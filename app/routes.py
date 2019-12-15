from flask import render_template, request
from app import app
import time
from web3 import Web3, HTTPProvider

contract_address = 


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/buy')
def buy():
    sellers=[{"Name":"abc","CarbonCredits":10},{"Name":"def","CarbonCredits":20},{"Name":"xyz","CarbonCredits":50}]
    return render_template('buy.html',len=len(sellers),sellers=sellers)

@app.route('/send-request',methods=['GET', 'POST'])
def send_request():
    seller_data=request.form.to_dict()
    return render_template('send-request.html',data=seller_data)
    

@app.route('/sell', methods=['GET','POST'])
def sell():
    if request.method == 'POST':
        # INPUTS TO SMART CONTRACT addCredit
        # verified_certificate: string
        # address_of_owner: address
        # amount : uint256
        # ttl : seconds
        payload = {}
        payload['name_of_project'] = request.form.get('title')
        payload['reference_num'] = request.form.get('ref_num')
        payload['amount'] = request.form.get('amount')
        payload['time_period'] = request.form.get('time-period')
        #put certificate string in payload
        
    return render_template('sell.html')

@app.route('/requests')
def requests():
    requests=[{"Name":"abc","CarbonCredits":10},{"Name":"def","CarbonCredits":20},{"Name":"xyz","CarbonCredits":50}]
    return render_template('requests.html',len=len(requests),requests=requests)

