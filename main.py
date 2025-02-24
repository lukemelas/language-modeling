import argparse, os
import torch
import torch.nn as nn
from torch.autograd import Variable
import torchtext

from train import train_model
from valid import validate_model
from utils import Logger, sample, preprocess, predict
from models.rnn import RNNLM
from models.ngram import NgramModel

parser = argparse.ArgumentParser(description='Language Model')
parser.add_argument('--model', metavar='DIR', default=None, help='path to model')
parser.add_argument('--lr', default=2e-3, type=float, metavar='N', help='learning rate')
parser.add_argument('--hs', default=300, type=int, metavar='N', help='size of hidden state')
parser.add_argument('--nlayers', default=1, type=int, metavar='N', help='number of layers in rnn')
parser.add_argument('--no-wt', dest='wt', action='store_false', help='disable weight tying in network')
parser.add_argument('--maxnorm', default=1.0, type=float, metavar='N', help='maximum gradient norm for clipping')
parser.add_argument('--dropout', default=0.0, type=float, metavar='N', help='dropout probability')
parser.add_argument('-v', default=10000, type=int, metavar='N', help='vocab size')
parser.add_argument('--data', default='./data', help='path to data')
parser.add_argument('-b', default=10, type=int, metavar='N', help='batch size')
parser.add_argument('--bptt', default=32, type=int, metavar='N', help='backprop though time length (sequence length)')
parser.add_argument('--epochs', default=15, type=int, metavar='N', help='number of epochs')
parser.add_argument('--ngram', dest='ngram', action='store_true', help='use ngram language model')
parser.add_argument('-e', '--evaluate', dest='evaluate', action='store_true', help='run model only on validation set')
parser.add_argument('-p', '--predict', dest='predict', action='store_true', help='save predictions on final input data')
parser.add_argument('--sample', default=0, type=int, help='number of sentences to sample')
parser.set_defaults(wt=True, ngram=False, evaluate=False, predict=False)

def main():
  global args
  args = parser.parse_args()
  use_gpu = torch.cuda.is_available()

  # Load and process data
  TEXT, train_iter, val_iter = preprocess(args.data, args.v, args.b, args.bptt)
  print('Loaded data')
  
  # Create model
  embedding = TEXT.vocab.vectors.clone()
  if args.ngram: 
    model = NgramModel(train_iter, TEXT)
  else:
    model = RNNLM(embedding, args.hs, args.nlayers, args.bptt, args.dropout, args.wt) 

  # Load pretrained model 
  if args.model is not None and os.path.isfile(args.model):
    model.load_state_dict(torch.load(args.model))
    print('Loaded pretrained model.')
  model = model.cuda() if use_gpu else model

  # Create loss function and optimizer
  criterion = nn.CrossEntropyLoss()
  optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=args.lr) 
  
  # Create logger and log hyperparameters
  logger = Logger()
  logger.log('''model: {m}
    optimizer: {o}
    learning rate: {lr}
    hidden_size: {hs}
    num_layers: {nl}
    max_norm: {mn}
    vocab size: {v}
    '''.format(m=model, o=optimizer, lr=args.lr, hs=args.hs, nl=args.nlayers, mn=args.maxnorm, v=args.v), stdout=False)
    
  # Train or validate model 
  if args.evaluate or args.ngram:
    validate_model(val_iter, model, criterion, TEXT, logger=logger)
    if args.predict:
      predict(model, args.data, TEXT)
      return 
  else:
    train_model(train_iter, val_iter, model, criterion, optimizer, TEXT, max_norm=args.maxnorm, num_epochs=args.epochs, logger=logger)

  # Sample from model
  if args.sample is not 0:
    for _ in range(args.sample):
      sent = sample(model, TEXT)
      print(sent)

  # Save predictions
  predict(model, args.data, TEXT)

  return

if __name__ == '__main__':
  main()
