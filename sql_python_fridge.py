
# FRIDGE INVENTORY TRACKER (PYTHON + SQL)

#Fridge_spoilage_tracker

from sqlite3 import *
from datetime import datetime
from tabulate import tabulate
from datetime import date
import pandas as pd
import requests
import schedule
import time

Headers=['ID','Name','Category','Price','Quantity','Date_of_Purchase','Date_of_Expiry','Days_left',
         'Status']
category_map={
      '1':'Dairy',
      '2':'Vegetables',
      '3':'Fruits',
      '4':'Grains',
      '5':'Protein',
      '6':'Other'}

TOKEN = "IS with Me"
CHAT_ID = "Is with Me"

def main_menu():
  while True:
    print("\n🧊 Welcome to Fridge Inventory Tracker")
    print("1. Add Item")
    print("2. View Fridge")
    print("3. View Spoiled Items")
    print("4. Remove items")
    print("5. Do you want to enable Daily alerts? (YES/NO) : ").strip().lower()
    print("6. Exit")
    choice = input("Choose an option: ")


    if choice =='1':
      name = input("Enter item name: ").capitalize()
      category = categories()
      if not category: continue
      price = float(input("Enter price Rs : "))
      quantity=int(input('Enter the Quantity: '))
      expiry_date = input("Enter expiry date (YYYY-MM-DD): ")
      purchase_date = input("Enter purchase date (YYYY-MM-DD) or press Enter to use today: ")
      purchase_date = purchase_date if purchase_date.strip() else None
      add_inventory(name,category, price, purchase_date, expiry_date, None, Quantity=quantity)

    elif choice =='2':
      status_refresher()
      view_fridge()

    elif choice =='3':
      status_refresher()
      view_spoiled()

    elif choice =='4':
      status_refresher()
      remove_items()

    elif choice=='5':
      if choice =='yes':
        start_schdeuler()
      else:
        print('Scheduler no running..........')
      print('Exiting.......')
      break

    elif choice =='6':
      print("Thank you for using <......> ")
      break    
    else:
      print('Invalid choice...please Try again properly')

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def Sqlbase():
  permission = connect("fridge.db")
  cursor= permission.cursor()
  cursor.execute('''
  CREATE TABLE IF NOT EXISTS products(
    ID Integer PRIMARY KEY AUTOINCREMENT,
    Name Text not null,
    Category Text not null,
    Price Real not null,
    Quantity Integer not null,
    Date_of_Purchase Text not null,
    Date_of_Expiry Text not null,
    Days_Left Integer,
    Status Text,
    Last_alert text
  )
  ''')
  permission.commit()
  permission.close()

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def categories():
  cat=str(input('Choose categories \n 1.Dairy \n 2.Vegetables \n 3.Fruits \n 4.Grains \n 5.Protein \n 6.Other :'))

  if cat in category_map:
    cate=category_map[cat]
    print(f'{cate} is added')
    return cate

  else:
    print('Invalid entry')
    return None

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def add_inventory(Name,Category,Price,PurchaseDate,ExpiryDate,DaysLeft,Quantity=1,Status='ACTIVE'):

  if not PurchaseDate:
    PurchaseDate = datetime.now().strftime("%Y-%m-%d")

  if ExpiryDate:
    DaysLeft = (datetime.strptime(ExpiryDate, "%Y-%m-%d") - datetime.now()).days
  else:
    DaysLeft = 0

  # Merge if the same product + expiry

  permission = connect("fridge.db")
  cursor = permission.cursor()

  cursor.execute('''
  SELECT ID, Quantity FROM products WHERE Name =? AND Date_Of_Expiry=?
   ''',(Name,ExpiryDate))
  existing=cursor.fetchall()

  if existing:
    cursor.execute("UPDATE products SET Quantity = Quantity + ? WHERE ID = ? "
    ,(Quantity,existing[0][0]))
  else:
    cursor.execute('''
    INSERT INTO products (
      Name,
      Category,
      Price,
      Quantity,
      Date_of_Purchase,
      Date_of_Expiry,
      Days_Left,
      Status)
      VALUES(?,?,?,?,?,?,?,?)
    ''',(Name,Category,Price,Quantity,PurchaseDate,ExpiryDate,DaysLeft,Status))
  permission.commit()
  permission.close()
  print(f"{Name} added successfully")

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Show current inventory
def view_fridge():

  category_filter = input(
        "\nWhat would you like to see inside the fridge?\n"
        "↳ Press Enter to view all items OR\n"
        "↳ Enter category name (e.g., Dairy, Fruits, etc): "
    ).capitalize().strip()

  permission = connect("fridge.db")
  query='SELECT * FROM products'

  if category_filter:
    query+=f"WHERE Category= '{category_filter}'"

  df=pd.read_sql_query(query,permission)
  permission.close()

  if not df.empty:
    print(tabulate(df, headers="keys", tablefmt='grid'))
  else:
    print("No items found.")
  permission.close()

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Spoiled only view:
def view_spoiled():

    permission = connect("fridge.db")
    cursor= permission.cursor()

    cursor.execute("SELECT * FROM products WHERE Status = 'SPOILED' ")
    spoiled=cursor.fetchall()

    if spoiled:
      print(tabulate(spoiled,headers=Headers,tablefmt='grid'))
    else:
      print('No Spoiled_items found')
    permission.close()

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def telegram_message(message):

  url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
  load = {"chat_id":CHAT_ID,"text":message}

  try:
    requests.post(url,data=load)
    print("Alert Sent Successfully")
  except Exception as e:
    print("Error sending alert:",e)

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Refreshes the status:

def status_refresher():

  permission = connect("fridge.db")
  cursor= permission.cursor()

  #update DaysLeft
  cursor.execute('''
  UPDATE products
  SET Days_Left = CAST(
    (julianday(Date_of_Expiry)-julianday('now')) AS INTEGER
    )
    ''')
  
  # Mark spoiled where DaysLeft<=0 and status is still ACTIVE
  cursor.execute('''
  UPDATE products
  SET Status='SPOILED'
  WHERE Days_Left < 0 and Status ='ACTIVE'
  ''')

  permission.commit()
  permission.close()

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def remove_items():

  try:
    option=int(input("Would like you to delete JUST ONE THING or every SPOILED THING - Select: (1 or 2): "))
  except ValueError:
    print("INVALID entry")
    return

  if option == 1:
    remove_this()
  elif option==2:
    remove_spoiled()
  else:
    print("Try Again")

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def remove_this():

  permission= connect("fridge.db")
  cursor=permission.cursor()

  view_fridge()

  try:
    item_ID= int(input("\n Enter the ID : "))
  except ValueError:
    print("Invalid ID.")
    permission.close()
    return

  cursor.execute("SELECT Quantity, Name FROM products WHERE ID = ? ",(item_ID,))
  item=cursor.fetchone()

  if not item:
    print(" item with this ID is not found ")
    permission.close()
    return

  current_qty, item_name=item #sequence unpacking as the query returns a tuple (2,tofu)

  try:
    remove_qty = int(input(f"Enter quantity to remove (Available: {current_qty}): ").strip())
  except ValueError:

    print("Invalid quantity.")
    permission.close()
    return

  if remove_qty <= 0:
    print("Please enter a positive quantity.")
    permission.close()
    return

  if remove_qty>=current_qty:
    confirm=str(input(f"You request to remove {remove_qty},but only this quantity is available {current_qty} should I remove everything (y/n)? : ")).strip().lower()

    if confirm=='y':
      cursor.execute("DELETE FROM products WHERE ID = ? ",(item_ID,))
      print(f"{item_name} removed completely")
    else:
      print("Aborted. No changes made")
  else:
    cursor.execute("UPDATE products SET Quantity = Quantity - ? WHERE ID = ? ",(remove_qty,item_ID))
    print(f"Removed {remove_qty} of '{item_name}'. Remaining {current_qty - remove_qty}")

  permission.commit()
  permission.close()

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def remove_spoiled():

  permission=connect("fridge.db")
  cursor=permission.cursor()

  cursor.execute("SELECT COUNT(*) FROM products WHERE Status = 'SPOILED'")
  count=cursor.fetchone()[0]

  if count == 0:
    print("No Spoiled items present to remove")
    permission.close()
  else:
    cursor.execute("DELETE FROM products WHERE Status = 'SPOILED' ")
    permission.commit()
    print(f"Removed {count} spoiled items.")

  permission.close()

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# BATCH - ALERTER :

def send_alert():
  
  # Refresh the DB before alert
  status_refresher()

  permission=connect("fridge.db")
  cursor=permission.cursor()

  cursor.execute("""
    SELECT ID, Name, Date_of_Expiry 
    FROM products
    WHERE julianday(Date_of_Expiry) - julianday('now') BETWEEN 0 AND 3
    AND (Last_alert IS NULL OR Last_alert!=(date('now')))
""")
  
  to_alert = cursor.fetchall()

  for item_id , item_name, expiry_date in to_alert:
    days_left =(date.fromisoformat(expiry_date) - date.today()).days
    message=f"⚠️ {item_name} with ID {item_id} will expire in {days_left} days !"
    telegram_message(message)


    cursor.execute('''
        UPDATE products
        SET Last_alert = date('now')
        WHERE ID = ?;
''',(item_id,))
    
  permission.commit()
  permission.close()
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# JOB - SCHEDULER :

def job():
  print("Running Daily check.......")
  send_alert()

def start_schdeuler():
  schedule.every().day.at("09:00").do(job)
  print("Scheduler started! Press CTRL+C to stop.......")

  try:
    while True:
      schedule.run_pending()
      time.sleep(60)
  except:
    print("Stopped manually.....")

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

if __name__=="__main__":
  Sqlbase()
  main_menu()