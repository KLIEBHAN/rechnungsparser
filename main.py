import os
import sys
import re
import argparse
import tkinter as tk
from tkinter import messagebox, simpledialog
import dateparser
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
REMOTE_HTTP_URL = 'http://VMTATEX:3000'
new_file_name = None

# Functions
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
    except (ValueError):
        raise ValueError("Rechnungsdatum kann nicht geparst werden.")
    return parsed_date.date()


@contextmanager
def sftp_connection(server, username, password):
    """Öffnet eine SFTP-Verbindung."""
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None
    with pysftp.Connection(server, username=username, password=password, cnopts=cnopts) as sftp:
        yield sftp

def moveToServer(pdf_path, remote_path):
    """Lädt PDF-Datei auf den Server."""
    with sftp_connection(REMOTE_SERVER, REMOTE_USERNAME, REMOTE_PASSWORD) as sftp:
        sftp.put(pdf_path, remote_path)
def choose_remote_path():
    """Lässt den Benutzer den Remotepfad auswählen."""
    chosen_path = tk.StringVar()  # Neue StringVar Variable

    def set_path(path):
        """Setzt den Wert der chosen_path-Variable."""
        chosen_path.set(path)
        path_dialog.destroy()

    path_dialog = tk.Toplevel()
    path_dialog.title("Remotepfad auswählen")

    path_1_button = tk.Button(
        path_dialog,
        text=REMOTE_PATHS['path_1'],
        command=lambda: set_path(REMOTE_PATHS['path_1']))
    path_1_button.pack(pady=(0, 3))

    path_2_button = tk.Button(
        path_dialog,
        text=REMOTE_PATHS['path_2'],
        command=lambda: set_path(REMOTE_PATHS['path_2']))
    path_2_button.pack(pady=(0, 3))

    quit_button = tk.Button(
        path_dialog,
        text="Beenden",
        command=path_dialog.destroy)
    quit_button.pack(pady=(0, 3))

    path_dialog.wait_window()

    while not chosen_path.get():
        path_dialog.wait_window()

    return chosen_path.get()  # Rückgabe des Wertes der chosen_path Variable



def show_info(titel, message):
    """Erstellen einer benutzerdefinierten Dialogbox"""
    def close_dialog():
        custom_dialog.destroy()
    custom_dialog = tk.Toplevel()
    custom_dialog.title(titel)


    # Setzen Sie die Größe des Fensters
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
    message = f'''{invoice_date_german}\n
{invoice_data['invoice_number']}\n
{invoice_data['amount']}\n\n\n
{invoice_data['text']}'''
    show_info("Rechnungsdaten",message)


def rename_file(pdf_path,invoice_data):
    """Benennt die Datei um und verschiebt sie."""
    global new_file_name


    invoice_date = invoice_data['date'].strftime('%Y_%m_%d')
    invoice_number = invoice_data['invoice_number']

    new_file_name = simpledialog.askstring(
        title="Dateiname",
        prompt="Neuen Namen anpassen.\t\t\t",
        initialvalue=f"{invoice_date}_{invoice_number}.pdf")
    os.rename(pdf_path, new_file_name)
    messagebox.showinfo("Erfolgreich", f"Erfolgreich zu {invoice_date}_{invoice_number}.pdf umbenannt")


def move_file():
    remote_path = choose_remote_path()
    moveToServer(new_file_name, remote_path + new_file_name)
    messagebox.showinfo("Erfolgreich", "Erfolgreich hochgeladen")

def post_invoice_data(invoice_data):
    """Sendet die Rechnungsdaten an einen Server."""
    response = httpx.post(REMOTE_HTTP_URL, json=invoice_data)

    if response.status_code != 201:
        raise Exception("Failed to post invoice data: " + response.text)


def choose_action(pdf_path, invoice_data):
    """Lässt den Benutzer die gewünschte Aktion auswählen."""
    global new_file_name
    action_dialog = tk.Toplevel()
    action_dialog.title("Aktion auswählen")

    show_invoice_data_button = tk.Button(
        action_dialog,
        text="Rechnungsdaten anzeigen",
        command=lambda: show_invoice_data(invoice_data))
    show_invoice_data_button.pack(pady=(0, 3))

    rename_file_button = tk.Button(
        action_dialog,
        text="Datei umbenennen",
        command=lambda: rename_file(pdf_path,invoice_data))
    rename_file_button.pack(pady=(0, 3))


    move_file_button = tk.Button(
        action_dialog,
        text="Datei hochladen",
        command=lambda: move_file())
    move_file_button.pack(pady=(0, 3))


    post_data_button = tk.Button(
        action_dialog,
        text="Rechnungsdaten senden",
        command=lambda: post_invoice_data(invoice_data))
    post_data_button.pack(pady=(0, 3))

    quit_button = tk.Button(
        action_dialog,
        text="Beenden",
        command=action_dialog.destroy)
    quit_button.pack(pady=(0, 3))

    action_dialog.wait_window()



def main(pdf_path):
    """Hauptfunktion des Programms."""
    global new_file_name
    if not pdf_path:
        sys.exit("Es wurde keine PDF-Datei ausgewählt.")

    try:
        root = tk.Tk()
        root.withdraw()


        text = extract_text_from_pdf(pdf_path)
        invoice_data = extract_invoice_data(text)
        invoice_data['date'] = parse_date(invoice_data['date'])
        invoice_data['text'] = text
        new_file_name = pdf_path

        choose_action(pdf_path, invoice_data)

        root.destroy()
    except ValueError as e:
        messagebox.showinfo("Error", f"Fehler: {str(e)}")
        sys.exit(f"Fehler: {str(e)}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pdf_path', nargs='?', default=None)
    args = parser.parse_args()
    main(args.pdf_path)
