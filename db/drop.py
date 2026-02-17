import sqlite3

conn = sqlite3.connect('community_of_practice.db')
cursor = conn.cursor()
cursor.execute('DROP TABLE IF EXISTS reviews')
print ('Successfull')

conn.commit()
conn.close()