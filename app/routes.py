from flask import render_template, request, flash, redirect, url_for
from functools import wraps
from app import app
import time
from .contract_abi import abi
from web3 import Web3, HTTPProvider
from Crypto.Hash import SHA256
import os, json
from .config import *
Session = {}

w3 = Web3(HTTPProvider('http://localhost:7545'))
contract = w3.eth.contract(address=CONTRACT_ADDR, abi = abi)

data_store = {}
purchase_request_store={}
user_store = {}

# functions to update JSON files which mock the databases
def initialize_file(file_name):
    filesize = os.path.getsize(file_name)

    if filesize == 0:
        return {}
    else: 
        with open(file_name, 'r') as filep:
            return json.load(filep)

# functions to update JSON files which mock the databases
def update_file(file_name, variable):
    with open(file_name, 'w') as filep:
        json.dump(variable, filep)

user_store = initialize_file('user_store.json')
data_store = initialize_file('data_store.json')
purchase_request_store = initialize_file('purchase_request_store.json')

def addCredits(certificate, owner, amount, ttl):
    print("Inside addCredit")
    nonce = w3.eth.getTransactionCount(WALLET_ADDRESS)
    txn_dict =contract.functions.addCredits(certificate, w3.toChecksumAddress(owner), int(amount), int(ttl)).buildTransaction({
        'nonce':nonce
    })
    signed_txn = w3.eth.account.signTransaction(txn_dict, private_key=WALLET_PRIVATE_KEY)
    result = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
    tx_receipt = w3.eth.getTransactionReceipt(result)
    count = 0

    while tx_receipt is None and count < 30:
        time.sleep(20)
        tx_receipt = w3.eth.getTransactionReceipt(result)
    
    if tx_receipt is None:
        return False, -1
    uuid = int(tx_receipt['logs'][0]['data'], 16)
    return True, uuid

def generate_hash(data):
    return SHA256.new(data).hexdigest()

def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in Session:
            return f(*args, **kwargs)
        else:
            flash('UNAUTHORIZED! Login required')
            return redirect(url_for('login'))
    return wrap

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        wallet_address = request.form.get('wallet-address')
        user_store[username] = {'password':password, 'wallet_address':wallet_address}
        update_file('user_store.json', user_store)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':    
        username = request.form.get('username')
        print(username)
        if username is None:
            return render_template('page-login.html')
        print(user_store.keys(), username)
        if username not in user_store.keys():
            return """
                <h1>Incorrect username</h1>
            """
        if(user_store[username]['password'] == request.form.get('password')):
            Session['username'] = username
            Session['logged_in'] = True
            return redirect(url_for('index'))
    return render_template('page-login.html')

@app.route('/')
@app.route('/index')
@login_required
def index():
    return render_template('index.html', notif="", ds = data_store, session=Session)

@app.route('/profile')
@login_required
def profile():
    return render_template('page-profile.html', username = Session['username'], wallet_address=user_store[Session['username']]['wallet_address'])

@app.route('/buy')
@login_required
def buy():
    # Prevent buying of self-owned carbon credits
    internal_dict = {}
    seller_dict = {}
    for key in data_store.keys():
        if key != user_store[Session['username']]['wallet_address']:
            internal_dict = data_store[key]
            seller_dict[key] = internal_dict

    return render_template('buy.html',sellers=seller_dict, buyer=user_store[Session['username']], session=Session)

@app.route('/send-request',methods=['GET', 'POST'])
@login_required
def send_request():
    if request.method =='POST':
        seller_data = request.form.to_dict()
        if seller_data['wallet-address'] in purchase_request_store.keys():
            purchase_request_store[seller_data['wallet-address']].append(seller_data)
        else:
            purchase_request_store[seller_data['wallet-address']] = [seller_data]

        update_file('purchase_request_store.json', purchase_request_store)    
        return redirect(url_for('index'))

    return render_template('send-request.html',data=seller_data, session=Session)
    

@app.route('/sell', methods=['GET','POST'])
@login_required
def sell():
    if user_store[Session['username']]['wallet_address'] != WALLET_ADDRESS:
        return """
            <h3>Access Denied</h3>
        """
    if request.method == 'POST':
        # INPUTS TO SMART CONTRACT addCredit
        # verified_certificate: string
        # address_of_owner: address
        # amount : uint256
        # ttl : seconds
        payload = {}
        payload['name_of_project'] = request.form.get('title')
        payload['reference_num'] = request.form.get('ref-num')
        payload['amount'] = request.form.get('amount')
        payload['time_period'] = request.form.get('time-period')
        addr = request.form.get('wallet-address')
        save_dir = os.path.join(os.getcwd(), 'xyz.pdf')

        # Save newly created Carbon Credit to blockchain
        try :
            with open(save_dir, "rb") as signed_doc:
                signed_doc_str = signed_doc.read()
                print(type(signed_doc_str))
                signed_doc_hash = generate_hash(signed_doc_str)
                print(signed_doc_hash)
                result, uuid= addCredits(signed_doc_hash, addr, payload['amount'], int(payload['time_period'])*30*86400)
                print("CHECK", result, uuid)
                if (result):
                    payload['uuid'] = uuid
                    if addr in data_store.keys():
                        data_store[addr].append(payload)
                    else:
                        data_store[addr] = [payload]
                    # CHANGE THIS -> update made to data_store !!!
                    update_file('data_store.json', data_store)
                    return render_template("index.html", notif = "Certificate added to blockchain", ds = data_store)
                else:
                    return render_template("index.html", notif = "Failed!2", ds= data_store)
        except Exception as e:
            print(e)
            return render_template("index.html", notif = "Failed!", ds= data_store)

    return render_template('sell.html', session=Session)

@app.route('/requests')
@login_required
def requests():
    requests = []
    key = user_store[Session['username']]['wallet_address']
 
    if key not in purchase_request_store.keys():
        print('No pending requests')
    else: 
        requests = purchase_request_store[user_store[Session['username']]['wallet_address']]
        print(requests)
        print(len(requests))

    return render_template('requests.html',len=len(requests),requests=requests, session=Session)


@app.route('/logout')
@login_required
def logout():
    Session.pop('logged_in')
    Session.pop('username')

    return redirect(url_for('login'))

@app.route('/accept', methods=['GET','POST'])
@login_required
def accept():
    print('/accept is called')
    if request.method == "POST": 
        data =  request.get_json()
        print(data['i'])
        current_obj = purchase_request_store[user_store[Session['username']]['wallet_address']].pop(int(data['i']))
        curr_list = data_store[current_obj['wallet-address']]
        count = 0
        idx = 0
        for item in curr_list:
            if item['reference_num'] == current_obj['reference-num']:
                idx = count
            count+=1
        
        if current_obj['receiver-wallet-address'] in data_store.keys():
            data_store[current_obj['receiver-wallet-address']].append(data_store[current_obj['wallet-address']][idx])
        else:
            data_store[current_obj['receiver-wallet-address']] = [(data_store[current_obj['wallet-address']][idx])]
        data_store[current_obj['wallet-address']].pop(idx)

        update_file('data_store.json', data_store)
        return redirect(url_for('requests'))

    return redirect(url_for('requests'))

@app.route('/reject/<index>')
@login_required
def reject(index):
    print('/reject is called')
    print('index :', index)
    current_obj = purchase_request_store[user_store[Session['username']]['wallet_address']].pop(int(index))
    update_file('purchase_request_store.json', purchase_request_store)

    return redirect(url_for('requests'))

# helper function used to convert wallet address to a username
def address_to_username(_address):
    for username in user_store.keys():
        if _address == user_store[username]['wallet_address']:
            return username
    
    return 'NONE'
 
# global transaction history 
@app.route('/transaction_history')
def transaction_history():
    transaction_history = {}
    internal_dict = {}
    count = 0
 
    latest_block_number = w3.eth.blockNumber
    
    # block number starts with 1
    for i in range(1, latest_block_number + 1):
        transaction_count = w3.eth.getBlockTransactionCount(i)
        for j in range(0, transaction_count):
            internal_dict = {}
            internal_dict['to'] = w3.eth.getTransactionByBlock(i, j)['to']
            internal_dict['to_username'] = address_to_username(internal_dict['to'])
            internal_dict['from'] = w3.eth.getTransactionByBlock(i, j)['from']
            internal_dict['from_username'] = address_to_username(internal_dict['from'])
            internal_dict['hash'] = (w3.eth.getTransactionByBlock(i, j)['hash']).hex()
            count = count + 1
            transaction_history[count] = internal_dict
    
    return render_template('transaction-history.html', transaction = transaction_history)
 
# transaction history of a particular user
@app.route('/user_transaction_history')
@login_required
def user_transaction_history():
    user_transaction_history = {}
    user_internal_dict = {}
    current_user = user_store[Session['username']]['wallet_address']
    count = 0
 
    latest_block_number = w3.eth.blockNumber
    # block number starts with 1
    for i in range(1, latest_block_number + 1):
        transaction_count = w3.eth.getBlockTransactionCount(i)
        for j in range(0, transaction_count):
            if  w3.eth.getTransactionByBlock(i, j)['to'] == current_user or  w3.eth.getTransactionByBlock(i, j)['from'] == current_user:
                user_internal_dict = {}
                user_internal_dict['to'] = w3.eth.getTransactionByBlock(i, j)['to']
                user_internal_dict['to_username'] = address_to_username(user_internal_dict['to'])
                user_internal_dict['from'] = w3.eth.getTransactionByBlock(i, j)['from']
                user_internal_dict['from_username'] = address_to_username(user_internal_dict['from'])
                user_internal_dict['hash'] = (w3.eth.getTransactionByBlock(i, j)['hash']).hex()
                # change made here
                count = count + 1
                user_transaction_history[count] = user_internal_dict
 
    # no transaction made or received by user
    if user_transaction_history == {}:
        return render_template('blank-transaction-history.html')
    else:
        return render_template('transaction-history.html', transaction = user_transaction_history)
 
@login_required
def go_to_user_history():
    return redirect(url_for('user_transaction_history'))
