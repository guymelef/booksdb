import csv
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def main():
    file = open("books.csv")
    reader = csv.reader(file)
    next(reader) # skip header row of books.csv
    for isbn, title, author, year in reader:
        db.execute("INSERT INTO library (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)",
                    {"isbn": isbn, "title": title, "author": author, "year": year})
        print(f"Added {title} (ISBN: {isbn}) by {author} ({year}).")
    db.commit()
    print("*************\n")
    print("HUGE SUCCESS!\n")
    print("*************\n")

if __name__ == "__main__":
    main()