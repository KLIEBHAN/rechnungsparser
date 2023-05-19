import os
import re

import httpx
import pysftp
import PyPDF2
import tkinter as tk
from tkinter import messagebox, simpledialog
import dateparser
from contextlib import contextmanager

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

# Hilfsfunktion zum Erstellen eines Buttons
def create_button(dialog, text, command):
    """Erstellt einen Button."""
    button = tk.Button(dialog, text=text, command=command)
    button.pack(pady=(0, 3))


# Funktion zur Extraktion von Text aus einer PDF-Datei
def extract_text_from_pdf(pdf_path):
    """Extrahiert den Text aus einer PDF-Datei."""
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ''.join([pdf_reader.pages[i].extract_text() for i in range(len(pdf_reader.pages))])
    return text


# Funktion zur Extraktion von Rechnungsdaten aus Text
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


# Funktion zum Parsen von Datumswerten aus einer Zeichenkette
def parse_date(date_str):
    """Analysiert das Datum aus einer Zeichenkette."""
    try:
        parsed_date = dateparser.parse(date_str)
    except ValueError:
        raise ValueError("Rechnungsdatum kann nicht geparst werden.")
    return parsed_date.date()


# Kontextmanager zur Verwaltung von SFTP-Verbindungen
@contextmanager
def sftp_connection(server, username, password):
    """Öffnet eine SFTP-Verbindung."""
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None
    with pysftp.Connection(server, username=username, password=password, cnopts=cnopts) as sftp:
        yield sftp


# Funktion zum Verschieben einer Datei zum Server
def move_to_server(pdf_path, remote_path):
    """Lädt PDF-Datei auf den Server."""
    with sftp_connection(REMOTE_SERVER, REMOTE_USERNAME, REMOTE_PASSWORD) as sftp:
        sftp.put(pdf_path, remote_path)


# Funktion zur Auswahl zwischen zwei Optionen
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


# Funktion zum Anzeigen von Informationen
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


# Funktion zum Anzeigen von Rechnungsdaten
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


# Funktion zum Setzen des Betreffs
def set_subject(invoice_data):
    invoice_data['subject'] = simpledialog.askstring(
        title="Betreff",
        prompt="Betreff eingeben.\t\t\t",
        initialvalue=f"{invoice_data['subject']}")


# Funktion zum Umbenennen einer Datei
def rename_file(invoice_data):
    """Benennt die Datei um und verschiebt sie."""
    pdf_path = invoice_data['new_file_name']
    invoice_date = invoice_data['date'].strftime('%Y_%m_%d')
    invoice_number = invoice_data['invoice_number']

    invoice_data['new_file_name'] = simpledialog.askstring(
        title="Dateiname",
        prompt="Neuen Namen anpassen.\t\t\t",
        initialvalue=f"{invoice_date}_{invoice_data['subject']}_{invoice_number}.pdf")
    os.rename(pdf_path, invoice_data['new_file_name'])
    messagebox.showinfo("Erfolgreich", f"Erfolgreich zu {invoice_data['new_file_name']} umbenannt")


# Funktion zum Verschieben einer Datei
def move_file(invoice_data):

    print(invoice_data['new_file_name'])
    remote_path = choose_between_two_options(
        "Remotepfad auswählen",
        REMOTE_PATHS['path_1'],
        REMOTE_PATHS['path_2'])

    move_to_server(invoice_data['new_file_name'], remote_path + invoice_data['new_file_name'])
    messagebox.showinfo("Erfolgreich", "Erfolgreich hochgeladen")


# Funktion zum Senden von Rechnungsdaten an einen Server
def post_invoice_data(invoice_data, datum, hinbuchung):
    """Sendet die Rechnungsdaten an einen Server."""

    rechnungstyp = choose_between_two_options(
        "Rechnungstyp auswählen",
        "Amazon Betriebsbedarf",
        "Amazon Bürobedarf")

    if hinbuchung:
        if rechnungstyp == "Amazon Betriebsbedarf":
            konto1 = "4980"
        else:
            konto1 = "4930"
        konto2 = "90000"
    else:
        konto1 = "90000"
        konto2 = "1200"

    data_to_post = {
        "date": datum.strftime('%d.%m.%Y'),
        "rechnungstext": rechnungstyp + f" RN {invoice_data['invoice_number']} {invoice_data['subject']}",
        "betrag": invoice_data['amount'],
        "konto1": konto1,
        "konto2": konto2
    }

    try:
        response = httpx.post(REMOTE_HTTP_URL, json=data_to_post)
    except Exception as e:
        messagebox.showinfo("Error", f"Unerwarteter Fehler: {str(e)}")

    if response.status_code != 201:
        messagebox.showinfo("Error", f"Failed to post invoice data: {response.text}")
