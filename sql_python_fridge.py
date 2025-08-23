
# FRIDGE INVENTORY TRACKER (PYTHON + SQL)

#Fridge_spoilage_tracker

from datetime import datetime
from tabulate import tabulate
from datetime import date
import pandas as pd
import sqlite3
import requests
import schedule
import time

Headers=['ID','Name','Category','Price','Quantity','Date_of_Purchase','Date_of_Expiry','Days_left',
         'Status','Last_alert']
category_map={
      '1':'Dairy',
      '2':'Vegetables',
      '3':'Fruits',
      '4':'Grains',
      '5':'Protein',
      '6':'Other'}

TOKEN = "7998919402:AAHh7w3-1rfs1kKUJe9wkIIKCOUD9m7MSLI"
CHAT_ID = "975979041"

class Database:
  
  def __init__(self,db_name="fridge.db"):
    self.db_name=db_name
    self.create_table()

  def connect(self):
    return sqlite3.connect(self.db_name)

  def create_table(self):
    with self.connect() as permission:
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
         
    
class Inventory(Database):

  def add_inventory(self,Name,Category,Price,PurchaseDate,ExpiryDate,DaysLeft,Quantity=1,Status='ACTIVE'):

    if not PurchaseDate:
      PurchaseDate = datetime.now().strftime("%Y-%m-%d")

    if ExpiryDate:
      DaysLeft = (datetime.strptime(ExpiryDate, "%Y-%m-%d") - datetime.now()).days
    else:
      DaysLeft = 0

    # Merge if the same product + expiry

    with self.connect() as permission:

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
      
    print(f"{Name} added successfully")

  #-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  # Refreshes the status:

  def status_refresher(self):

    with self.connect() as permission:

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
      

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  def remove_items(self):

    try:
      option=int(input("Would like you to delete JUST ONE THING or every SPOILED THING - Select: (1 or 2): "))
    except ValueError:
      print("INVALID entry")
      return

    if option == 1:
      self.remove_this()
    elif option==2:
      self.remove_spoiled()
    else:
      print("Try Again")

    #-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

  def remove_this(self):

    with self.connect() as permission:
      cursor=permission.cursor()

      self.view_fridge()

      try:
        item_ID= int(input("\n Enter the ID : "))
      except ValueError:
        print("Invalid ID.")
        
        return

      cursor.execute("SELECT Quantity, Name FROM products WHERE ID = ? ",(item_ID,))
      item=cursor.fetchone()

      if not item:
        print(" item with this ID is not found ")
        
        return

      current_qty, item_name=item #sequence unpacking as the query returns a tuple (2,tofu)

      try:
        remove_qty = int(input(f"Enter quantity to remove (Available: {current_qty}): ").strip())
      except ValueError:

        print("Invalid quantity.")
        
        return

      if remove_qty <= 0:
        print("Please enter a positive quantity.")
        
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
      
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

  def remove_spoiled(self):

     with self.connect() as permission:
      cursor=permission.cursor()

      cursor.execute("SELECT COUNT(*) FROM products WHERE Status = 'SPOILED'")
      count=cursor.fetchone()[0]

      if count == 0:
        print("No Spoiled items present to remove")
        
      else:
        cursor.execute("DELETE FROM products WHERE Status = 'SPOILED' ")
        permission.commit()
        print(f"Removed {count} spoiled items.")
    

class Notifier(Inventory):
  
  def __init__(self, token: str, chat_id: str):
        super().__init__("fridge.db")
        self.TOKEN = token
        self.CHAT_ID = chat_id
  
  
  def telegram_message(self,message):

    url=f"https://api.telegram.org/bot{self.TOKEN}/sendMessage"
    load = {"chat_id":self.CHAT_ID,"text":message}

    try:
      requests.post(url,data=load)
      print("Alert Sent Successfully")
    except Exception as e:
      print("Error sending alert:",e)

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  def send_alert(self):
  
# Refresh the DB before alert
    self.status_refresher()

    with self.connect() as permission:

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
        self.telegram_message(message)


        cursor.execute('''
            UPDATE products
            SET Last_alert = date('now')
            WHERE ID = ?;
    ''',(item_id,))
        
      permission.commit()

# JOB - SCHEDULER :

  def job(self):
      print("Running Daily check.......")
      self.send_alert()

  def start_scheduler(self):
      schedule.every().day.at("09:00").do(self.job)
      print("Scheduler started! Press CTRL+C to stop.......")

      try:
        while True:
          schedule.run_pending()
          time.sleep(60)
      except KeyboardInterrupt:
        print("Stopped manually.....")



class FridgeApp(Notifier):
  
  def main_menu(self):

    while True:
      print("\n🧊 Welcome to Fridge Inventory Tracker")
      print("1. Add Item")
      print("2. View Fridge")
      print("3. View Spoiled Items")
      print("4. Remove items")
      print("5. Enable Daily Alerts ")
      print("6. Exit")
      choice = input("Choose an option: ")


      if choice =='1':
        name = input("Enter item name: ").capitalize()
        category = self.categories()
        if not category: continue
        price = float(input("Enter price Rs : "))
        quantity=int(input('Enter the Quantity: '))
        expiry_date = input("Enter expiry date (YYYY-MM-DD): ")
        purchase_date = input("Enter purchase date (YYYY-MM-DD) or press Enter to use today: ")
        purchase_date = purchase_date if purchase_date.strip() else None
        self.add_inventory(name,category, price, purchase_date, expiry_date, None, Quantity=quantity)

      elif choice =='2':
        self.status_refresher()
        self.view_fridge()

      elif choice =='3':
        self.status_refresher()
        self.view_spoiled()

      elif choice =='4':
        self.status_refresher()
        self.remove_items()

      elif choice=='5':

        ask = input("Enable daily alerts? (yes/no): ").strip().lower()
        if ask == "yes":
          self.start_scheduler()
        else:
          print("Scheduler not running...")

      elif choice =='6':
        print("Thank you for using <......> ")
        break    
      else:
        print('Invalid choice...please Try again properly')

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  
  def categories(self):

    cat=str(input('Choose categories \n 1.Dairy \n 2.Vegetables \n 3.Fruits \n 4.Grains \n 5.Protein \n 6.Other :')).strip()

    if cat in category_map:
      cate=category_map[cat]
      print(f'{cate} is added')
      return cate

    else:
      print('Invalid entry')
      return None
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  # Show current inventory
  def view_fridge(self):

    category_filter = input(
          "\nWhat would you like to see inside the fridge?\n"
          "↳ Press Enter to view all items OR\n"
          "↳ Enter category name (e.g., Dairy, Fruits, etc): "
      ).capitalize().strip()

    with self.connect() as permission:

      query='SELECT * FROM products'

      if category_filter:
        query+=f" WHERE Category= '{category_filter}'"

      df=pd.read_sql_query(query,permission)
      

      if not df.empty:
        print(tabulate(df, headers="keys", tablefmt='grid'))
      else:
        print("No items found.")
  

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Spoiled only view:
  def view_spoiled(self):

      with self.connect() as permission:

        cursor= permission.cursor()

        cursor.execute("SELECT * FROM products WHERE Status = 'SPOILED' ")
        spoiled=cursor.fetchall()

        if spoiled:
          print(tabulate(spoiled,headers=Headers,tablefmt='grid'))
        else:
          print('No Spoiled_items found')
      

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
if __name__=="__main__":
  app=FridgeApp(TOKEN,CHAT_ID)
  app.main_menu()