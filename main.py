import os
import sys
import re
import pdftotext
import argparse
from datetime import datetime

import tkinter as tk
from tkinter import messagebox, simpledialog
from dateutil import parser as date_parser
from contextlib import contextmanager

import pysftp


# Constants
PATTERNS = {
    'date': r'(?:Rechnungsdatum|Datum)\s*(?:\/Lieferdatum)?\s*((\d{1,2}[-./]\d{1,2}[-./]\d{2,4})|(\d{1,2}\s+\w+\s+\d{2,4}))',
    'invoice_number': r'(?:Rechnungsnummer|Rechnungs-Nr\.|Fakturanummer|Rechnungsnr\.|Invoice No\.?)\s*([A-Za-z0-9\-_]+)',
    'amount': r'(?:Zahlbetrag|Gesamtbetrag|Total)\s*([\d,.]+)\s*(?:€|EUR)?',
}
REMOTE_PATHS = {
    'path_1': '/C:/Daten/TATEX/Buchhaltung/2023/Buchungen/Rechnungen/2_Rechnungen_gebucht/',
    'path_2': '/C:/Daten/TATEX/Buchhaltung/2023/Buchungen/Rechnungen/3_Rechnungen_abgeschloßen/'
}
REMOTE_SERVER = 'VMTATEX'
REMOTE_USERNAME = "fabi"
REMOTE_PASSWORD = "/85fabI-19!"

# Functions
def extract_text_from_pdf(pdf_path):
    """Extrahiert den Text aus einer PDF-Datei."""
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = pdftotext.PDF(pdf_file)
        text = ''.join(page for page in pdf_reader)
    return text


def extract_invoice_data(text):
    """Extrahiert Rechnungsdaten aus dem Text."""
    return {key: re.search(pattern, text, re.IGNORECASE).group(1) for key, pattern in PATTERNS.items()}

def parse_date(date_str):
    """Analysiert das Datum aus einer Zeichenkette."""
    try:
        parsed_date = date_parser.parse(date_str, dayfirst=True).date()
    except (ValueError, TypeError):
        raise ValueError("Rechnungsdatum nicht gefunden.")
    return parsed_date


@contextmanager
def sftp_connection(server, username, password):
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None
    with pysftp.Connection(server, username=username, password=password, cnopts=cnopts) as sftp:
        yield sftp

def moveToServer(pdf_path, remote_path):
    with sftp_connection(REMOTE_SERVER, REMOTE_USERNAME, REMOTE_PASSWORD) as sftp:
        sftp.put(pdf_path, remote_path)

def choose_remote_path():
    """Lässt den Benutzer den Remotepfad auswählen."""
    question_text = (f"Welcher Remotepfad soll verwendet werden?\n"
                 f"Yes -> {REMOTE_PATHS['path_1']}\n"
                 f"No -> {REMOTE_PATHS['path_2']}")
    result = messagebox.askquestion("Pfad", question_text, type='yesno', default='yes')
    return REMOTE_PATHS['path_1'] if result == 'yes' else REMOTE_PATHS['path_2']

def show_invoice_data(invoice_data):
    """Zeigt die extrahierten Rechnungsdaten an."""
    invoice_date_german = invoice_data['date'].strftime('%d.%m.%Y')
    message = (f"{invoice_date_german}\n"
               f"{invoice_data['invoice_number']}\n"
               f"{invoice_data['amount']}")
    messagebox.showinfo("Rechnungsdaten", message)

def rename_and_move_file(pdf_path, new_file_name):
    """Benennt die Datei um und verschiebt sie."""
    os.rename(pdf_path, new_file_name)


    move_file = messagebox.askyesno("Verschieben?", f"Möchten Sie die Datei {new_file_name} auf den Server verschieben?")
    if move_file:
        remote_path = choose_remote_path()
        moveToServer(new_file_name, remote_path + new_file_name)
        messagebox.showinfo("Erfolgreich", "Erfolgreich hochgeladen")

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
        show_invoice_data(invoice_data)
        invoice_date = invoice_data['date'].strftime('%Y_%m_%d')
        invoice_number = invoice_data['invoice_number']
        new_file_name = f"{invoice_date}_{invoice_number}.pdf"
        rename_file = messagebox.askyesno("Umbenennen?", f"Möchten Sie die Datei {pdf_path} umbenennen?")

        if rename_file:
            new_file_name = simpledialog.askstring(
                title="Dateiname",
                prompt="Neuen Namen anpassen.\t\t\t",
                initialvalue=new_file_name)
            rename_and_move_file(pdf_path, new_file_name)

        root.destroy()
    except ValueError as e:
        sys.exit(f"Fehler: {str(e)}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pdf_path', nargs='?', default=None)
    args = parser.parse_args()
    main(args.pdf_path)
