import hashlib
import json
from textwrap import dedent
from uuid import uuid4
import jsonpickle
from flask import Flask
from urllib.parse import urlparse
from Crypto.PublicKey import RSA
from Crypto.Signature import *
from time import time
from datetime import datetime
import requests


class Blockchain(object):
    # Inicializa a blockchain
    def __init__(self):
        self.chain = [self.addGenesisBlock()]
        #
        self.pendingTransactions = []

        # Blockchains possuem suas transações organizadas em fila, é necessário inicializar uma lista
        self.difficulty = 3
        # Transação como recompensa de por mineração
        self.minerRewards = 5  # * len(self.pendingTransactions)
        self.blockSize = 1
        self.nodes = set()
        self.chain = [self.addGenesisBlock()]

    def addTransaction(self, sender, reciever, amt, fee, keyString, senderKey):
        # Checa se o remetente tem o valor a ser transferido

        if amt > self.getBalance(sender):
            print("Saldo Insuficiente")
            # print(self.getBalance(sender))
            return False

        # Importa as chaves tanto do remetente quanto do destinatário

        keyByte = keyString.encode("ASCII")
        senderKeyByte = senderKey.encode("ASCII")

        key = RSA.import_key(keyByte)
        senderKey = RSA.import_key(senderKeyByte)

        # Valida se os demais atributos constam corretamente na transação
        if not sender or not reciever or not amt:
            print("transaction error 1")
            return False

        # Gera uma nova transação
        transaction = Transaction(sender, reciever, amt, fee)

        # assina a transação recém criada
        transaction.signTransaction(key, senderKey)

        # valida se a assinatura da transação está correta
        if not transaction.isValidTransaction():
            print("transaction error 2")
            return False

        # Adiciona uma nova transação a ser minerada e aumenta o tamanho da blockchain
        self.pendingTransactions.append(transaction)
        return len(self.chain) + 1

    # Gera chaves privadas e publicas para
    def generateKeys(self):
        # Define key, uma chave de chave RSA de 2048 bits
        key = RSA.generate(2048)
        # Exporta a chave privada recém gerada
        private_key = key.export_key()
        file_out = open("private.pem", "wb")
        file_out.write(private_key)
        # Exporta a chave pública recém gerada
        public_key = key.publickey().export_key()
        file_out = open("receiver.pem", "wb")
        file_out.write(public_key)

        # print(public_key.decode("ASCII"))
        return key.publickey().export_key().decode("ASCII")

    # Retorna o balanço do usuárui checando os blocos da blockchain
    def getBalance(self, person):
        balance = 0
        for i in range(0, len(self.chain)):
            block = self.chain[i]
            try:
                for j in range(0, len(block.transactions)):
                    transaction = block.transactions[j]
                    if transaction.sender == person:
                        balance -= transaction.amt + transaction.fee
                    if transaction.reciever == person:
                        balance += transaction.amt
            except AttributeError:
                print("no transaction")
        return balance

    def minePendingTransactions(self, miner):
        # Checa se há transações para minerar
        lenPT = len(self.pendingTransactions)
        if lenPT < 1:
            print("No transactions to mine!\n#############")
            return False

        # Checa o valor total da taxa de mineração
        fee = 0
        for i in range(0, lenPT, self.blockSize):
            end = i + self.blockSize
            if i >= lenPT:
                end = lenPT

            transactionSlice = self.pendingTransactions[i:end]

            for transaction in transactionSlice:
                fee = +transaction.fee
                if self.getBalance(transaction.sender) < transaction.amt:
                    del transactionSlice[transactionSlice.index(transaction)]
                    print("invalid transaction\n#############")

            newBlock = Block(
                transactionSlice,
                datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
                len(self.chain),
            )

            if newBlock.transactions != []:
                newBlock.prev = self.getLastBlock().hash

                # print(newBlock.prev)
                newBlock.mineBlock(self.difficulty)
                self.chain.append(newBlock)
                print("Transaction Block Mined!")

                rewardBlock = Block(
                    [Transaction("Miner Rewards", miner, fee, 0)],
                    datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
                    len(self.chain),
                )

                hashVal2 = self.getLastBlock().hash
                # print(hashVal2)
                rewardBlock.prev = hashVal2
                rewardBlock.mineBlock(self.difficulty)
                print("Reward Block Mined!")
                if fee != 0:
                    self.chain.append(rewardBlock)
                    print("Mining Reward:", fee)
        print("Mining Transactions Success!\n#############")

        # payMiner = Transaction("Miner Rewards", miner, fee, 0)
        self.pendingTransactions = []
        return True

    # Busca pelo bloco anterior da cadeia
    def getLastBlock(self):
        return self.chain[-1]

    def addGenesisBlock(self):
        tArr = []
        tArr.append(Transaction("Blockchain", "Heber", 100, 0))
        genesis = Block(tArr, datetime.now().strftime("%m/%d/%Y, %H:%M:%S"), 0)

        genesis.prev = "None"

        return genesis

    # Cria um novo bloco na cadeia, se baseando no bloco anterior, caso não haja um, sinaliza como bloco anterior vazio
    # def addBlock(self, block):
    #     if len(self.chain) > 0:
    #         block.prev = self.getLastBlock().hash
    #     else:
    #         block.prev = "none"
    #     self.chain.append(block)

    # Monta um arquivo JSON do estado da blockchain
    def chainJSONencode(self):
        blockArrJSON = []
        for block in self.chain:
            blockJSON = {}
            blockJSON["hash"] = block.hash
            blockJSON["index"] = block.index
            blockJSON["prev"] = block.prev
            blockJSON["time"] = block.time
            blockJSON["nonce"] = block.nonce

            transactionsJSON = []
            tJSON = {}
            for transaction in block.transactions:
                tJSON["time"] = transaction.time
                tJSON["sender"] = transaction.sender
                tJSON["reciever"] = transaction.reciever
                tJSON["amt"] = transaction.amt
                tJSON["fee"] = transaction.fee
                tJSON["hash"] = transaction.hash
                transactionsJSON.append(tJSON)

            blockJSON["transactions"] = transactionsJSON

            blockArrJSON.append(blockJSON)

        return blockArrJSON

    def chainJSONdecode(self, chainJSON):
        chain = []
        for blockJSON in chainJSON:
            tArr = []
            for tJSON in blockJSON["transactions"]:
                transaction = Transaction(
                    tJSON["sender"], tJSON["reciever"], tJSON["amt"], tJSON["fee"]
                )
                transaction.time = tJSON["time"]
                transaction.hash = tJSON["hash"]
                tArr.append(transaction)

            block = Block(tArr, blockJSON["time"], blockJSON["index"])
            block.hash = blockJSON["hash"]
            block.prev = blockJSON["prev"]
            block.nonse = blockJSON["nonse"]

            chain.append(block)
        return chain


class Block(object):
    def __init__(self, transactions, time, index):
        # Número do Bloco
        self.index = index
        # Lista de transações
        self.transactions = transactions
        # Tempo da criação do bloco
        self.time = time
        # Hash do bloco anterior
        self.prev = ""
        # Nonce do bloco. Nonce é o número/hash que é utilizado na prova de trabalho do bloco
        self.nonce = 0
        # Hash do bloco atual
        self.hash = self.calculateHash()

    def calculateHash(self):
        hashTransactions = ""
        for transaction in self.transactions:
            hashTransactions += transaction.hash
        #  Cria uma String contentdo o tempo na qual o hash será criado, o hash da transação que criou esse bloco, o núnumero do hash do bloco anterior e o index desse bloco
        hashString = (
            str(self.time)
            + hashTransactions
            + self.prev
            + str(self.index)
            + str(self.nonce)
        )
        #  formata a String anterior como JSON
        hashEncoded = json.dumps(hashString, sort_keys=True).encode()
        #  Retorna o JSON anterior criptografado em SHA256 -> mesma criptografia do Bitcoin
        return hashlib.sha256(hashEncoded).hexdigest()

    def mineBlock(self, difficulty):
        arr = []
        for i in range(0, difficulty):
            arr.append(i)

        # compute until the beginning of the hash = 0123..difficulty
        arrStr = map(str, arr)
        hashPuzzle = "".join(arrStr)
        # print(len(hashPuzzle));
        while self.hash[0:difficulty] != hashPuzzle:
            self.nonce += 1
            self.hash = self.calculateHash()
            # print(len(hashPuzzle))
            # print(self.hash[0:difficulty])

            # EXIBIÇÃO DO PROCESSO DE MINERAÇÀO
            # print(self.nonce)
            # print("hash attempt", self.hash)
            # print("hash desejado", hashPuzzle)

        # print("Block Mined!")
        return True

    def hasValidTransactions(self):
        for i in range(0, len(self.transactions)):
            transaction = self.transactions[i]
            if not transaction.isValidTransaction():
                return False
            return True

    def JSONencode(self):
        return jsonpickle.encode(self)


class Transaction(object):
    # Inicialização da classe de Transaction
    def __init__(self, sender, reciever, amt, fee):
        # Define o remetente da transação
        self.sender = sender
        # Define o destinatário da transação
        self.reciever = reciever
        # Define Taxa de transação
        self.fee = fee
        # Define a quantidade de tokens a ser transferida
        self.amt = amt - self.fee
        # Define a data da transação
        self.time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        # Define o Hash de identificação da transação
        self.hash = self.calculateHash()

    def calculateHash(self):
        #  Cria uma String contentdo o tempo na qual o hash será criado, o remetente da transação e a quantidade de tokens a ser transferido
        hashString = self.sender + self.reciever + str(self.amt) + str(self.time)
        #  formata a String anterior como JSON
        hashEncoded = json.dumps(hashString, sort_keys=True).encode()
        #  Retorna o JSON anterior criptografado em SHA256 -> mesma criptografia do Bitcoin
        return hashlib.sha256(hashEncoded).hexdigest()

    def isValidTransaction(self):
        if self.amt <= 0:
            return False

        # Checa se o Hash da transação é o mesmo hash que o criado na transação
        if self.hash != self.calculateHash():
            return False
        # Checa se o destinatário da transação é o mesmo que o remetente
        if self.sender == self.reciever:
            return False
        # Checa se essa transação é resultante de uma mineração
        if self.sender == "Miner Rewards":
            # security : unfinished
            return True
        # Checa se a assinatura da transação consta a mesma do remetente
        if not self.signature or len(self.signature) == 0:
            print("No Signature!")
            return False
        # Caso todos os demais fatores estiverem corretos, valida a transferência

        return True

    def signTransaction(self, key, senderKey):
        # Checa se o Hash da transação é o mesmo hash que o criado na transação
        if self.hash != self.calculateHash():
            print("transaction tampered error")
            return False
        # print(str(key.publickey().export_key()));
        # print(self.sender);
        # Checa se a chave pública do remetente da transação é a mesma da chave na carteira do remetente
        if str(key.publickey().export_key()) != str(senderKey.publickey().export_key()):
            print("Transaction attempt to be signed from another wallet")
            return False

        # h = MD5.new(self.hash).digest();

        # Cria uma assinatura PKCS115
        pkcs1_15.new(key)

        self.signature = "made"
        # print(key.sign(self.hash, ""));
        print("made signature!")
        return True
