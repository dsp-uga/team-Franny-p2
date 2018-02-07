import argparse
import re
import json
import os.path
import numpy as np
import string
from operator import add

from pyspark import SparkContext

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "CSCI 8360 Project 2",
                                     epilog = "answer key", add_help = "How to use",
                                     prog = "python p1.py [training-data] [training-label] [testing-data] [optional args]")
        
    # Required args
    parser.add_argument("paths", nargs=3, #required = True
                        help = "Paths of training-data, training-labels, and testing-data.")
#    parser.add_argument("ptrain", help = "Directory of training data and labels")
#    parser.add_argument("ptest", help = "Directory of testing data and labels")

    # Optional args
#    parser.add_argument("-s", "--size", choices = ["vsmall", "small", "large"], default = "vsmall",
#                        help = "Sizes to the selected file: \"vsmall\": very small, \"small\": small, \"large\": large [Default: \"vsmall\"]")
    parser.add_argument("-o", "--output", default = ".",
                        help = "Path to the output directory where outputs will be written. [Default: \".\"]")
#    parser.add_argument("-a", "--accuracy", default = True,
#                        help = "Accuracy of the testing prediction [Default: True]")



    args = vars(parser.parse_args())
    sc = SparkContext()
    
    training_data = args['paths'][0]
    training_label = args['paths'][1]
    testing_data = args['paths'][2]

    raw_rdd_train_data = sc.textFile(training_data)
    pattern = re.compile(r'([\s])([A-F0-9]{2})([\s]+)([a-z]+)([\s+])')
    opcodes_rdd = raw_rdd_train_data.flatMap(lambda x: pattern.findall(x)).map(lambda x: x[3])
    opcodes_count_rdd = opcodes_rdd.map(lambda x: (x,1)).reduceByKey(add)
#    print(opcodes_count_rdd.collect())


