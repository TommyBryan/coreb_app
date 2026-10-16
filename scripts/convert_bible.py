"""One-off converter: scrollmapper `bible_databases` CSV -> COREB Bible CSV.

Source files (public domain), from
https://github.com/scrollmapper/bible_databases/tree/master/formats/csv
  KJV.csv    King James Version
  SpaRV.csv  Reina-Valera 1909

Usage:
  python scripts/convert_bible.py KJV.csv data/bible/kjv.csv --lang en
  python scripts/convert_bible.py SpaRV.csv data/bible/rv1909.csv --lang es

Output columns: book_order,book,chapter,verse,text
"""

import argparse
import csv

BOOKS_EN = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges",
    "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles",
    "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
    "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations",
    "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah",
    "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi", "Matthew",
    "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians",
    "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians",
    "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews",
    "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude", "Revelation",
]

BOOKS_ES = [
    "Génesis", "Éxodo", "Levítico", "Números", "Deuteronomio", "Josué", "Jueces",
    "Rut", "1 Samuel", "2 Samuel", "1 Reyes", "2 Reyes", "1 Crónicas",
    "2 Crónicas", "Esdras", "Nehemías", "Ester", "Job", "Salmos", "Proverbios",
    "Eclesiastés", "Cantares", "Isaías", "Jeremías", "Lamentaciones", "Ezequiel",
    "Daniel", "Oseas", "Joel", "Amós", "Abdías", "Jonás", "Miqueas", "Nahúm",
    "Habacuc", "Sofonías", "Hageo", "Zacarías", "Malaquías", "Mateo", "Marcos",
    "Lucas", "Juan", "Hechos", "Romanos", "1 Corintios", "2 Corintios", "Gálatas",
    "Efesios", "Filipenses", "Colosenses", "1 Tesalonicenses", "2 Tesalonicenses",
    "1 Timoteo", "2 Timoteo", "Tito", "Filemón", "Hebreos", "Santiago", "1 Pedro",
    "2 Pedro", "1 Juan", "2 Juan", "3 Juan", "Judas", "Apocalipsis",
]


def convert(src: str, dst: str, lang: str) -> None:
    names = BOOKS_ES if lang == "es" else BOOKS_EN
    order: dict[str, int] = {}
    written = 0
    with open(src, newline="", encoding="utf-8") as fin, \
            open(dst, "w", newline="", encoding="utf-8") as fout:
        writer = csv.writer(fout)
        writer.writerow(["book_order", "book", "chapter", "verse", "text"])
        for row in csv.DictReader(fin):
            text = (row["Text"] or "").strip()
            if not text:
                continue
            idx = order.setdefault(row["Book"], len(order) + 1)
            writer.writerow([idx, names[idx - 1], int(row["Chapter"]), int(row["Verse"]), text])
            written += 1
    if len(order) != 66:
        raise SystemExit(f"expected 66 books, found {len(order)}")
    print(f"{dst}: {written} verses")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("src")
    parser.add_argument("dst")
    parser.add_argument("--lang", choices=["en", "es"], default="en")
    args = parser.parse_args()
    convert(args.src, args.dst, args.lang)
