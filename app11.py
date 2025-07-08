from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        frequency = int(request.form['frequency'])
        location = request.form['location']
        if amount > 3000 and frequency < 2 and location.lower() == 'unknown':
            result = "Transaction potentiellement frauduleuse ⚠️"
        else:
            result = "Transaction légitime ✅"
        return render_template('predict.html', result=result)
    return render_template('predict.html')

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True)
