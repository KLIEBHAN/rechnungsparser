import os
import sys
import re
import argparse
import tkinter as tk
from tkinter import messagebox, simpledialog
import dateparser
from datetime import date
from contextlib import contextmanager
import PyPDF2
import pysftp
import httpx

# Constants
INVOICE_PATTERNS = {
    'date': r'(?:Rechnungsdatum|Datum)\s*(?:\/Lieferdatum)?\s*((\d{1,2}[-./]\d{1,2}[-./]\d{2,4})|(\d{1,2}[.]?\s+\w+\s+\d{2,4}))',
    'invoice_number': r'(?:Rechnungsnummer|Rechnungs-Nr\.|Fakturanummer|Rechnungsnr\.|Invoice No\.)\s*([A-Za-z0-9\-_]+)',
    'amount': r'(?:Zahlbetrag|Gesamtbetrag|Total|Rechnungsbetrag)\s*([\d,.]+)\s*(?:€|EUR)?',
}

REMOTE_PATHS = {
    'path_1': '/C:/Daten/TATEX/Buchhaltung/2023/Buchungen/Rechnungen/2_Rechnungen_gebucht/',
    'path_2': '/C:/Daten/TATEX/Buchhaltung/2023/Buchungen/Rechnungen/3_Rechnungen_abgeschloßen/'
}

REMOTE_SERVER = 'VMTATEX'
REMOTE_USERNAME = "fabi"
REMOTE_PASSWORD = "?"
REMOTE_HTTP_URL = 'http://VMTATEX:3000/json'


def extract_text_from_pdf(pdf_path):
    """Extrahiert den Text aus einer PDF-Datei."""
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ''.join([pdf_reader.pages[i].extract_text() for i in range(len(pdf_reader.pages))])
    return text


def extract_invoice_data(text):
    """Extrahiert Rechnungsdaten aus dem Text."""
    invoice_data = {}
    for key, pattern in INVOICE_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            invoice_data[key] = match.group(1)
        else:
            raise ValueError(f"{key} nicht gefunden.")
    return invoice_data

def parse_date(date_str):
    """Analysiert das Datum aus einer Zeichenkette."""
    try:
        parsed_date = dateparser.parse(date_str)
    except ValueError:
        raise ValueError("Rechnungsdatum kann nicht geparst werden.")
    return parsed_date.date()


@contextmanager
def sftp_connection(server, username, password):
    """Öffnet eine SFTP-Verbindung."""
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None
    with pysftp.Connection(server, username=username, password=password, cnopts=cnopts) as sftp:
        yield sftp


def move_to_server(pdf_path, remote_path):
    """Lädt PDF-Datei auf den Server."""
    with sftp_connection(REMOTE_SERVER, REMOTE_USERNAME, REMOTE_PASSWORD) as sftp:
        sftp.put(pdf_path, remote_path)


def choose_between_two_options(text, option1, option2):
    chosen_option = tk.StringVar()

    def set_option(option):
        chosen_option.set(option)
        path_dialog.destroy()

    path_dialog = tk.Toplevel()
    path_dialog.title(text)

    path_1_button = tk.Button(
        path_dialog,
        text=option1,
        command=lambda: set_option(option1))
    path_1_button.pack(pady=(0, 3))

    path_2_button = tk.Button(
        path_dialog,
        text=option2,
        command=lambda: set_option(option2))
    path_2_button.pack(pady=(0, 3))

    path_dialog.wait_window()

    while not chosen_option.get():
        path_dialog.wait_window()

    return chosen_option.get()


def show_info(titel, message):
    """Erstellen einer benutzerdefinierten Dialogbox"""
    def close_dialog():
        custom_dialog.destroy()
    custom_dialog = tk.Toplevel()
    custom_dialog.title(titel)
    custom_dialog.geometry("300x200")

    text_widget = tk.Text(custom_dialog, wrap=tk.WORD, padx=3, pady=3)
    text_widget.insert(tk.END, message)
    text_widget.configure(state='disabled')
    text_widget.pack(expand=True, fill=tk.BOTH)

    ok_button = tk.Button(custom_dialog, text="OK", command=close_dialog)
    ok_button.pack(pady=(0, 3))

    custom_dialog.wait_window()


def show_invoice_data(invoice_data):
    """Zeigt die extrahierten Rechnungsdaten an."""
    invoice_date_german = invoice_data['date'].strftime('%d.%m.%Y')
    message = f'''
{invoice_data['new_file_name']}\n
{invoice_date_german}\n
{invoice_data['invoice_number']}\n
{invoice_data['amount']}\n\n\n
{invoice_data['text']}'''
    show_info("Rechnungsdaten", message)


def set_subject(invoice_data):
    invoice_data['subject'] = simpledialog.askstring(
        title="Betreff",
        prompt="Betreff eingeben.\t\t\t",
        initialvalue=f"{invoice_data['subject']}")

def rename_file(pdf_path, invoice_data):
    """Benennt die Datei um und verschiebt sie."""
    invoice_date = invoice_data['date'].strftime('%Y_%m_%d')
    invoice_number = invoice_data['invoice_number']

    invoice_data['new_file_name'] = simpledialog.askstring(
        title="Dateiname",
        prompt="Neuen Namen anpassen.\t\t\t",
        initialvalue=f"{invoice_date}_{invoice_data['subject']}_{invoice_number}.pdf")
    os.rename(pdf_path, invoice_data['new_file_name'])
    messagebox.showinfo("Erfolgreich", f"Erfolgreich zu {invoice_date}_{invoice_number}.pdf umbenannt")


def move_file(invoice_data):
    remote_path = choose_between_two_options(
        "Remotepfad auswählen",
        REMOTE_PATHS['path_1'],
        REMOTE_PATHS['path_2'])

    move_to_server(invoice_data['new_file_name'], remote_path + invoice_data['new_file_name'])
    messagebox.showinfo("Erfolgreich", "Erfolgreich hochgeladen")

def post_invoice_data(invoice_data, datum, hinbuchung):
    """Sendet die Rechnungsdaten an einen Server."""

    rechnungstyp = choose_between_two_options(
        "Rechnungstyp auswählen",
        "Amazon Betriebsbedarf",
        "Amazon Bürobedarf")

    if hinbuchung:
        if(rechnungstyp == "Amazon Betriebsbedarf"):
            konto1 = "4980"
        else:
            konto1 = "4930"
        konto2 = "90000"
    else:
        konto1 = "90000"
        konto2 = "1200"


    data_to_post ={
        "date": datum.strftime('%d.%m.%Y'),
        "rechnungstext": rechnungstyp + f" RN {invoice_data['invoice_number']} {invoice_data['subject']}",
        "betrag": invoice_data['amount'],
        "konto1": konto1,
        "konto2": konto2
    }

    response = httpx.post(REMOTE_HTTP_URL, json=data_to_post)

    if response.status_code != 201:
        raise Exception("Failed to post invoice data: " + response.text)



def choose_action(pdf_path, invoice_data):
    """Lässt den Benutzer die gewünschte Aktion auswählen."""
    action_dialog = tk.Toplevel()
    action_dialog.title("Aktion auswählen")

    show_invoice_data_button = tk.Button(
        action_dialog,
        text="Rechnungsdaten anzeigen",
        command=lambda: show_invoice_data(invoice_data))
    show_invoice_data_button.pack(pady=(0, 3))

    set_subject_button = tk.Button(
        action_dialog,
        text="Betreff setzen",
        command=lambda: set_subject(invoice_data))
    set_subject_button.pack(pady=(0, 3))

    rename_file_button = tk.Button(
        action_dialog,
        text="Datei umbenennen",
        command=lambda: rename_file(pdf_path, invoice_data))
    rename_file_button.pack(pady=(0, 3))

    move_file_button = tk.Button(
        action_dialog,
        text="Datei hochladen",
        command=lambda: move_file(invoice_data))
    move_file_button.pack(pady=(0, 3))

    post_data_button = tk.Button(
        action_dialog,
        text="Rechnungsdaten senden - Hinbuchung",
        command=lambda: post_invoice_data(invoice_data, invoice_data['date'], 1))
    post_data_button.pack(pady=(0, 3))

    post_data_button = tk.Button(
        action_dialog,
        text="Rechnungsdaten senden - Rückbuchung",
        command=lambda: post_invoice_data(invoice_data, date.today(), 0))
    post_data_button.pack(pady=(0, 3))

    quit_button = tk.Button(
        action_dialog,
        text="Beenden",
        command=action_dialog.destroy)
    quit_button.pack(pady=(0, 3))

    action_dialog.wait_window()


def main(pdf_path):
    """Hauptfunktion des Programms."""
    if not pdf_path:
        sys.exit("Es wurde keine PDF-Datei ausgewählt.")

    try:
        root = tk.Tk()
        root.withdraw()
        text = extract_text_from_pdf(pdf_path)
        invoice_data = extract_invoice_data(text)
        invoice_data['date'] = parse_date(invoice_data['date'])
        invoice_data['text'] = text
        invoice_data['new_file_name'] = pdf_path
        invoice_data['subject'] = ""

        choose_action(pdf_path, invoice_data)

        root.destroy()
    except ValueError as e:
        messagebox.showinfo("Error", f"Fehler: {str(e)}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pdf_path', nargs='?', default=None)
    args = parser.parse_args()
    main(args.pdf_path)
