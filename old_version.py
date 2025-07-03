# pip install scikit-learn pandas numpy python-telegram-bot

from telegram.ext import Updater, MessageHandler, Filters
from telegram import ParseMode
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.tree import DecisionTreeClassifier
import numpy as np
import logging
import Responses 
import pandas as pd 
import Constants as keys 


keywords = list(Responses.responses.keys())
answers = list(Responses.responses.values())

labels, uniques = pd.factorize(answers)

vectorizer = CountVectorizer()
X = vectorizer.fit_transform(keywords)

clf = DecisionTreeClassifier()
clf.fit(X, labels)

def label_to_answer(label_idx: int) -> str:
    return uniques[label_idx]



def handle_message(update, context):
    user_text = update.message.text.lower()


    X_test = vectorizer.transform([user_text])
    if X_test.nnz == 0:  
        update.message.reply_text("No he entendido tu pregunta. ¿Puedes reformularla?")
        return

    pred_label = clf.predict(X_test)[0]
    respuesta = label_to_answer(pred_label)
    update.message.reply_text(respuesta, parse_mode=ParseMode.HTML)


def main():

    updater = Updater(token=keys.KEY_TELEGRAM, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
