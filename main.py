import os
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog
import PyPDF2
import re
import argparse
from datetime import datetime
import pysftp


patterns = {
    'date': r'Rechnungsdatum\s*(?:\/Lieferdatum)?\s*((\d{1,2}[-./]\d{1,2}[-./]\d{2,4})|(\d{1,2}\s+\w+\s+\d{2,4}))',
    'invoice_number': r'(?:Rechnungsnummer|Rechnungs-Nr\.|Fakturanummer)\s*([A-Za-z0-9\-_]+)',
    'amount': r'Zahlbetrag\s*([\d,.]+)\s*€',
}
remote_path_1 = '/C:/Daten/TATEX/Buchhaltung/2023/Buchungen/Rechnungen/2_Rechnungen_gebucht/'
remote_path_2 = '/C:/Daten/TATEX/Buchhaltung/2023/Buchungen/Rechnungen/3_Rechnungen_abgeschloßen/'
remote_server = 'VMTATEX'
remote_username = "fabi"
remote_password = "?"

def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        num_pages = len(pdf_reader.pages)
        text = ''.join(pdf_reader.pages[page].extract_text() for page in range(num_pages))
    return text


def extract_invoice_data(pdf_path):
    text = extract_text_from_pdf(pdf_path)

    # Extract date
    match = re.search(patterns['date'], text, re.IGNORECASE)
    if match:
        invoice_date_str = match.group(1)
        if '-' in invoice_date_str or '.' in invoice_date_str:
            invoice_date = datetime.strptime(invoice_date_str, '%d.%m.%Y').date()
        else:
            invoice_date = datetime.strptime(invoice_date_str, '%d %B %Y').date()
    else:
        raise ValueError("Rechnungsdatum nicht gefunden.")

    # Extract invoice number
    match = re.search(patterns['invoice_number'], text, re.IGNORECASE)
    if match:
        invoice_number = match.group(1)
    else:
        raise ValueError("Rechnungsnummer nicht gefunden.")

    # Extract amount
    match = re.search(patterns['amount'], text, re.IGNORECASE)
    if match:
        amount_str = match.group(1)
    else:
        raise ValueError("Betrag nicht gefunden.")

    return {'date': invoice_date, 'invoice_number': invoice_number, 'amount': amount_str}


def moveToServer(pdf_path,remote_path):
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None  # ignore host key checking
    sftp = pysftp.Connection(remote_server, username=remote_username, password=remote_password, cnopts=cnopts)
    sftp.put(pdf_path, remote_path)
    sftp.close()

if __name__ == '__main__':

    pdf_path = False
    parser = argparse.ArgumentParser()
    parser.add_argument('pdf_path', nargs='?', default=None)
    args = parser.parse_args()
    pdf_path = args.pdf_path

    if not pdf_path:
        sys.exit("Es wurde keine PDF-Datei ausgewählt.")

    try:
        invoice_data = extract_invoice_data(pdf_path)
        invoice_date = invoice_data['date'].strftime('%Y_%m_%d')
        invoice_date_german = invoice_data['date'].strftime('%d.%m.%Y')
        invoice_number = invoice_data['invoice_number']
        amount = invoice_data['amount']
        message = f"Rechnungsdatum: {invoice_date_german}\nRechnungsnummer: {invoice_number}\nBetrag: {amount}€"
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Rechnungsdaten", message)
        new_file_name = f"{invoice_date}_{invoice_number}.pdf"

        rename_file = messagebox.askyesno("Umbenennen?", "Möchten Sie die Datei "+pdf_path+" umbenennen?")
        if rename_file:
            new_file_name = simpledialog.askstring(title = "Dateiname", prompt = "Neuen Namen anpassen.\t\t\t", initialvalue=new_file_name)
            os.rename(pdf_path, new_file_name)
        else:
            new_file_name = pdf_path


        move_file = messagebox.askyesno("Verschieben?", "Möchten Sie die Datei "+new_file_name+" auf den Server verschieben?")


        if move_file:
            remote_path = ""
            result = messagebox.askquestion(
                "Pfad", "Welcher Remotepfad soll verwendert werden?\nYes -> "+ remote_path_1+"\nNo -> " +remote_path_2,type='yesno',
                default='yes')
            if result == 'yes':
                remote_path = remote_path_1
            else:
                remote_path = remote_path_2
            moveToServer(new_file_name,remote_path+new_file_name)
            messagebox.showinfo("Erfolgreich","Erfolgreich hochgeladen")
        root.destroy()

    except ValueError as e:
        sys.exit(f"Fehler: {str(e)}")
