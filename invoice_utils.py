import os
import re
import tkinter as tk
from contextlib import contextmanager
from tkinter import messagebox, simpledialog
import PyPDF2
import dateparser
import httpx
import pysftp
import configparser

config = configparser.ConfigParser()
config.read('C:\\Users\\fabia\\git\\rechnungsparser\\rechnungsparser.cfg')

# Constants
INVOICE_PATTERNS = {
    'date': r'(?:Rechnungsdatum|Datum)\s*(?:\/Lieferdatum)?\s*((\d{1,2}[-./]\d{1,2}[-./]\d{2,4})|'
            r'(\d{1,2}[.]?\s+\w+\s+\d{2,4}))',
    'invoice_number': r'(?:Rechnungsnummer|Rechnungs-Nr\.|Fakturanummer|Rechnungsnr\.|Invoice No\.)'
                      r'\s*([A-Za-z0-9\-_]+)',
    'amount': r'(?:Zahlbetrag|Gesamtbetrag|Total|Rechnungsbetrag)\s*([\d,.]+)\s*(?:€|EUR)?',
}

REMOTE_PATHS = {
    'path_1': '/C:/Daten/TATEX/Buchhaltung/2023/Buchungen/Rechnungen/2_Rechnungen_gebucht/',
    'path_2': '/C:/Daten/TATEX/Buchhaltung/2023/Buchungen/Rechnungen/3_Rechnungen_abgeschloßen/'
}

REMOTE_SERVER = config['DEFAULT']['REMOTE_SERVER']
REMOTE_USERNAME = config['DEFAULT']['REMOTE_USERNAME']
REMOTE_PASSWORD = config['DEFAULT']['REMOTE_PASSWORD']
REMOTE_HTTP_URL = config['DEFAULT']['REMOTE_HTTP_URL']


# Helper function to create a button
def create_button(dialog, text, command):
    """Creates a button."""
    button = tk.Button(dialog, text=text, command=command)
    button.pack(pady=(0, 3))


# Function to extract text from a PDF file
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text from a PDF file."""
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ''.join([pdf_reader.pages[i].extract_text() for i in range(len(pdf_reader.pages))])
    return text


# Function to extract invoice data from text
def extract_invoice_data(text):
    """Extracts invoice data from text."""
    invoice_data = {}
    for key, pattern in INVOICE_PATTERNS.items():
        if match := re.search(pattern, text):
            invoice_data[key] = match[1]
        else:
            raise ValueError(f"{key} not found.")
    return invoice_data


def parse_date(date_str):
    """Parses a date value from a string."""
    try:
        parsed_date = dateparser.parse(date_str)
        if parsed_date is None:
            raise ValueError("Invalid date string: {}".format(date_str))
        return parsed_date.date()
    except ValueError:
        raise ValueError("Invalid date string: {}".format(date_str))


# Context manager for managing SFTP connections
@contextmanager
def sftp_connection(server, username, password):
    """Opens an SFTP connection."""
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None
    with pysftp.Connection(server, username=username, password=password, cnopts=cnopts) as sftp:
        yield sftp


# Function to move a file to the server
def move_to_server(pdf_path, remote_path):
    """Uploads PDF file to the server."""
    with sftp_connection(REMOTE_SERVER, REMOTE_USERNAME, REMOTE_PASSWORD) as sftp:
        sftp.put(pdf_path, remote_path)


# Function to choose between two options
def choose_between_two_options(text, option1, option2):
    chosen_option = tk.StringVar()

    def set_option(option):
        chosen_option.set(option)
        dialog.destroy()

    dialog = tk.Toplevel()
    dialog.title(text)

    create_button(dialog, option1, lambda: set_option(option1))
    create_button(dialog, option2, lambda: set_option(option2))

    dialog.wait_window()

    while not chosen_option.get():
        dialog.wait_window()

    return chosen_option.get()


# Function to show information
def show_info(title, message):
    """Creates a custom dialog box"""

    def close_dialog():
        custom_dialog.destroy()

    custom_dialog = tk.Toplevel()
    custom_dialog.title(title)
    custom_dialog.geometry("300x200")

    text_widget = tk.Text(custom_dialog, wrap=tk.WORD, padx=3, pady=3)
    text_widget.insert(tk.END, message)
    text_widget.configure(state='disabled')
    text_widget.pack(expand=True, fill=tk.BOTH)

    ok_button = tk.Button(custom_dialog, text="OK", command=close_dialog)
    ok_button.pack(pady=(0, 3))

    custom_dialog.wait_window()


# Function to show invoice data
def show_invoice_data(invoice_data):
    """Displays the extracted invoice data."""
    invoice_date_german = invoice_data['date'].strftime('%d.%m.%Y')
    message = f'''
{invoice_data['new_file_name']}\n
{invoice_date_german}\n
{invoice_data['invoice_number']}\n
{invoice_data['amount']}\n\n\n
{invoice_data['text']}'''
    show_info("Rechnungsdaten", message)


# Function to set the subject
def set_subject(invoice_data):
    invoice_data['subject'] = simpledialog.askstring(
        title="Betreff",
        prompt="Betreff eingeben.\t\t\t",
        initialvalue=f"{invoice_data['subject']}")


# Function to rename a file
def rename_file(invoice_data):
    """Renames the file and moves it."""
    pdf_path = invoice_data['new_file_name']
    invoice_date = invoice_data['date'].strftime('%Y_%m_%d')
    invoice_number = invoice_data['invoice_number']

    invoice_data['new_file_name'] = simpledialog.askstring(
        title="Dateiname",
        prompt="Neuen Namen anpassen.\t\t\t",
        initialvalue=f"{invoice_date}_{invoice_data['subject']}_{invoice_number}.pdf")
    os.rename(pdf_path, invoice_data['new_file_name'])
    messagebox.showinfo("Erfolgreich", f"Erfolgreich zu {invoice_data['new_file_name']} umbenannt")


# Function to move a file
def move_file(invoice_data):
    remote_path = choose_between_two_options(
        "Remotepfad auswählen",
        REMOTE_PATHS['path_1'],
        REMOTE_PATHS['path_2'])

    move_to_server(invoice_data['new_file_name'], remote_path + invoice_data['new_file_name'])
    messagebox.showinfo("Erfolgreich", "Erfolgreich hochgeladen")


def assign_kontos(rechnungstyp, hinbuchung):
    """Assigns the accounts based on the invoice type and booking."""
    if hinbuchung:
        konto1 = "4980" if rechnungstyp == "Amazon Betriebsbedarf" else "4930"
        konto2 = "90000"
    else:
        konto1 = "90000"
        konto2 = "1200"

    return konto1, konto2


def create_data_to_post(invoice_data, datum, konto1, konto2, rechnungstyp):
    """Creates the data to be sent to the server."""
    return {
        "date": datum.strftime('%d.%m.%Y'),
        "rechnungstext": f"{rechnungstyp} RN {invoice_data['invoice_number']} {invoice_data['subject']}",
        "betrag": invoice_data['amount'],
        "konto1": konto1,
        "konto2": konto2,
    }


def post_data(data_to_post):
    """Sends the data to the server."""
    try:
        response = httpx.post(REMOTE_HTTP_URL, json=data_to_post)
        if response.status_code != 201:
            messagebox.showinfo("Error", f"Failed to post invoice data: {response.text}")
    except Exception as e:
        messagebox.showinfo("Error", f"Unerwarteter Fehler: {str(e)}")


def post_invoice_data(invoice_data, datum, hinbuchung):
    """Sends the invoice data to a server."""
    rechnungstyp = choose_between_two_options(
        "Rechnungstyp auswählen",
        "Amazon Betriebsbedarf",
        "Amazon Bürobedarf"
    )
    konto1, konto2 = assign_kontos(rechnungstyp, hinbuchung)
    data_to_post = create_data_to_post(invoice_data, datum, konto1, konto2, rechnungstyp)
    post_data(data_to_post)