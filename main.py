import sys
import argparse
import tkinter as tk
from tkinter import messagebox
from datetime import date
from invoice_utils import (extract_text_from_pdf, extract_invoice_data, parse_date,
                           show_invoice_data, set_subject, rename_file,
                           move_file, post_invoice_data, create_button)
import os


# Funktion zur Auswahl der auszuführenden Aktion
def choose_action(invoice_data):
    """Lässt den Benutzer die gewünschte Aktion auswählen."""
    try:
        action_dialog = tk.Toplevel()
        action_dialog.title("Aktion auswählen")

        create_button(action_dialog, "Rechnungsdaten anzeigen", lambda: show_invoice_data(invoice_data))
        create_button(action_dialog, "Betreff setzen", lambda: set_subject(invoice_data))
        create_button(action_dialog, "Datei umbenennen", lambda: rename_file(invoice_data))
        create_button(action_dialog, "Datei hochladen", lambda: move_file(invoice_data))
        create_button(action_dialog, "Rechnungsdaten senden - Hinbuchung",
                      lambda: post_invoice_data(invoice_data, invoice_data['date'], 1))
        create_button(action_dialog, "Rechnungsdaten senden - Rückbuchung",
                      lambda: post_invoice_data(invoice_data, date.today(), 0))
        create_button(action_dialog, "Beenden", action_dialog.destroy)

        action_dialog.wait_window()
    except Exception as e:
        messagebox.showinfo("Error", f"Unerwarteter Fehler: {str(e)}")


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
        invoice_data['new_file_name'] = os.path.basename(pdf_path)
        invoice_data['subject'] = ""

        choose_action(invoice_data)

        root.destroy()
    except ValueError as e:
        messagebox.showinfo("Error", f"Fehler: {str(e)}")
    except Exception as e:
        messagebox.showinfo("Error", f"Unerwarteter Fehler: {str(e)}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pdf_path', nargs='?', default=None)
    args = parser.parse_args()
    main(args.pdf_path)
