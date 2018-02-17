# -*- coding: utf-8 -*-
"""
Created on Sat Feb 10 21:26:51 2018

@author: ailingwang

py2 GCP version. Most code is based on Weiwen Xu's work
"""

import re
import numpy as np
from operator import add

from pyspark import SparkContext
from pyspark.ml.feature import NGram
from pyspark.sql import SparkSession

from pyspark.ml.linalg import Vectors, VectorUDT
from pyspark.ml.feature import StringIndexer
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.classification import NaiveBayes,MultilayerPerceptronClassifier


from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder
from pyspark.sql.functions import concat, col,udf,struct
from itertools import chain
from pyspark.sql.types import *
from pyspark.ml.feature import Word2Vec
from pyspark.ml.feature import HashingTF
##


def build_full_feature_list(features,length):
#    print(features.shape())
#    print(length)
#    print("$$$$$$$$$$$")
    full_feature_narray = np.zeros(length,)
    full_feature_narray[features[:,0]] = features[:,1]
    return full_feature_narray
#    return [features.shape(),length]
    
    
def RF_feature_selection(td):    
    rf = RandomForestClassifier(numTrees=4, maxDepth=3, labelCol="label")
    model = rf.fit(td)  
    feature_importance = model.featureImportances
    return feature_importance

def RF_feature_filter(feature_importance,full_feature_wl):
    full_feature_rf = full_feature_wl.map(lambda x: (x[0],x[1],Vectors.dense([x[2][i] for i in feature_importance.indices])))
    print(len(full_feature_rf.take(1)[2][0]),full_feature_rf.take(1))
    td_new = create_td(full_feature_rf)
    return td_new


def change_column_datatype(td,col_name,datatype):
    
    td_new = td.withColumn(col_name, td[col_name].cast(datatype()))
    return td_new



def get_filename_label_pair(filenames_data_rdd,labels_rdd):
    """
        This function matches the filename with label
        
        --input-------------------------------------
        filenames_data_rdd : [<hash1>, <hash2>, ...]
        labels_rdd : [label1, label2, ...]
        
        --output------------------------------------
        filename_label_pair : [(<hash1>,<label1>), (<hash2>,<label2>), ...]
    """
    
    id_filenames_rdd = filenames_data_rdd.zipWithIndex().map(lambda x: (x[1],x[0]))
    id_label_rdd = labels_rdd.zipWithIndex().map(lambda x: (x[1],x[0]))
    filename_label_pair = id_filenames_rdd.join(id_label_rdd).map(lambda x: x[1])
    return filename_label_pair

def extract_opcode(file_data_rdd):
    """This function extract the ngram opcode counts
    It takes in file rdd, and number of grams to be calculated"""
    
     #---Extract opcodes--------------------------
    opcode_pattern = re.compile(r'([\s])([A-F0-9]{2})([\s]+)([a-z]+)([\s+])')
    opcodes_rdd = file_data_rdd.map(lambda x: (x[0],opcode_pattern.findall(x[1]))).flatMapValues(lambda x:x).map(lambda x: (x[0],x[1][3]))
    opcodes_rdd = opcodes_rdd.groupByKey().map(lambda x: (x[0],list(x[1])))
    return opcodes_rdd

def extract_segment(file_data_rdd):
    """     This function extract the ngram opcode counts"""    
    # ----Segment Count extraction--------------------
    
    segment_pattern = re.compile(r'([a-zA-Z]+):[a-zA-Z0-9]{8}[\t\s]')
    segment_rdd = file_data_rdd.map(lambda x: (x[0],segment_pattern.findall(x[1]))).flatMapValues(lambda x:x)
    segment_rdd = segment_rdd.groupByKey().map(lambda x: (x[0],list(x[1])))
    return segment_rdd


def preprocess(data_msd_folder, files,N):
    print("***********preprocessing******************")
    Spark_Full = sc.emptyRDD()
    myRDDlist = []
    for filename in files[:N]:
        new_rdd = sc.textFile(data_msd_folder +"/"+ filename + ".asm").map(lambda x: (filename,x)).groupByKey().map(lambda x: (x[0],' '.join(x[1])))
        myRDDlist.append(new_rdd)
        
    Spark_Full = sc.union(myRDDlist)
    return Spark_Full   

def concat(type):
    # referenced from stackoverflow
    def concat_(*args):
        return list(chain(*args))
    return udf(concat_, ArrayType(type))


def create_td(train_file_data_rdd,filename_label_pair,t):
    print("************** creating  ",t, " td****************")
    
    df_opcode = spark.createDataFrame(extract_opcode(train_file_data_rdd),['name','opcodes']).repartition(6000)
    ng = NGram(n=3, inputCol="opcodes", outputCol="words")

    df_features = ng.transform(df_opcode).drop("opcodes")
    #df_segment = spark.createDataFrame(extract_segment(train_file_data_rdd),['name1','segments']).repartition(6000)

    #df_features = df_ng_opcode.join(df_segment,df_ng_opcode.name == df_segment.name1).drop(df_segment.name1).repartition(6000)
    #concat_string_arrays = concat(StringType())
    
    #referenced from stackoverflow
    #list_to_vector_udf = udf(lambda l: Vectors.dense(l), VectorUDT())
    
    if t == "train":
        print("trainset")
        df_label = spark.createDataFrame(filename_label_pair,["file","label"])
        df_features = df_features.join(df_label,df_features.name == df_label.file)
        print("sss")
       # df_features = df_features.select("name","label",concat_string_arrays(col("ngram_opcodes"), col("segments")).alias("words"))\
            #.drop("ngram_opcodes").drop("segments")
        df_features = change_column_datatype(df_features,"label",DoubleType).repartition(6000)

    else:
        #df_features = df_features.select("name",concat_string_arrays(col("ngram_opcodes"), col("segments")).alias("words"))\
            #.drop("ngram_opcodes").drop("segments")
        df_features = df_features.withColumn("words", df_features.words).repartition(6000)
    
    return df_features
    
if __name__ == "__main__":
    
    # IDF threshold
    IDF = 2
    # Number of files for training
    
    sc = SparkContext()
    spark = SparkSession.builder.master("yarn").appName("Word Count").config("spark.some.config.option", "some-value").getOrCreate()
    data_msd_folder = "gs://uga-dsp/project2/data/asm/"
    training_file_names = "gs://uga-dsp/project2/files/X_train.txt"
    training_label = "gs://uga-dsp/project2/files/y_train.txt"
    test_file_names = "gs://uga-dsp/project2/files/X_test.txt"
    #test_label = "gs://uga-dsp/project2/files/y_small_test.txt"

        
    # Read in the data
    print("************Reading and preprocess data***************")
    rdd_label = sc.textFile(training_label)
    
    #test_rdd_label = sc.textFile(test_label)
    
    
    train_files_rdd =sc.textFile(training_file_names)
    test_files_rdd =sc.textFile(test_file_names)
    train_files = train_files_rdd.collect()
    test_files = test_files_rdd.collect()
    
    NUM_FILES = 6000
    T_NUM_FILES = len(test_files)
   
    sc.setCheckpointDir('checkpoint/')
    
    
    file_name_pattern = re.compile(r'([a-zA-Z0-9]+)\.asm')
  
    train_file_data_rdd = preprocess(data_msd_folder, train_files, NUM_FILES)
    train_file_data_rdd.persist()
    test_file_data_rdd = preprocess(data_msd_folder, test_files,T_NUM_FILES)#len(test_files.value))
    train_file_data_rdd.persist()
    print("there is number of training files: ",train_file_data_rdd.count())
    filename_label_pair = get_filename_label_pair(train_files_rdd,rdd_label)
    
    df_train = create_td(train_file_data_rdd,filename_label_pair,"train")
    df_train.persist()
    print( df_train.show())

    
    
    print("************Finished reading and preprocess data***************")
    
    
    print("*************** Start training feature selection *******************")   
    """
    hashingTF = HashingTF(inputCol="features", outputCol="rawFeatures", numFeatures=20)
    featurizedTrain = hashingTF.transform(df_train)
    
    distinct_features = featurizedTrain.head().rawFeatures
    print(distinct_features)
    print(featurizedTrain.show())
    """

    
    word2Vec = Word2Vec(vectorSize=500, minCount=2, inputCol="words", outputCol="features")
    model = word2Vec.fit(df_train)

    df_train_vec = model.transform(df_train)
    

    print("*************** Finished training feature selection *******************")
    

    print("*************** Start training ******************")
    
    #model = logistic_regression(opcode_RF)
    layers = [500, 50, 20, 9]

    # create the trainer and set its parameters
    oriModel = MultilayerPerceptronClassifier(maxIter=100, layers=layers, blockSize=128, seed=1234)

    # Fit the model
    #model = RF(opcode_RF)
    
    print("*************** Cross Validation****************")
    # reference from spark documentation
    
    evaluator = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="accuracy")
        
    paramGrid = ParamGridBuilder() \
    .addGrid(oriModel.layers, [[500, 50, 20, 9], [500,100, 9],[500, 100, 50, 9],[500, 30, 9]]) \
    .build()
    
    crossval = CrossValidator(estimator=oriModel,
                          estimatorParamMaps=paramGrid,
                          evaluator=evaluator,
                          numFolds=4)
    cvModel = crossval.fit(df_train_vec)
    #cvModel.save("gs://irene024082/cvmodel")
    #print(opcode_RF)
    
    train_result = cvModel.transform(df_train_vec)
    train_result = train_result.withColumn('prediction',train_result.prediction + 1)
    train_result.show()
    # Select (prediction, true label) and compute test error
   
    
    accuracy = evaluator.evaluate(train_result)
    print("Test Error = %g" % (1.0 - accuracy))
    
    print("**************Finish Evaluation RF training***************")
    

    
    #print(all_features_count.take(10))
    print("*************** Start Test transforming*******************")
    df_test = create_td(test_file_data_rdd,filename_label_pair,"test")
    df_test.persist()
    df_test_vec = model.transform(df_test)
    
    result = cvModel.transform(df_test_vec)
    result = result.repartition(30).withColumn("prediction", result["prediction"].cast("int"))
    result = result.withColumn('prediction',result.prediction + 1)
    result.show()

    """
    result = result.repartition(10).withColumn("prediction", result["prediction"].cast("double"))
    result_df = result.select("prediction","name")
    result_label_df = spark.createDataFrame(get_filename_label_pair(test_files_rdd,test_rdd_label)).toDF("name","label")
    result_df = result_df.join(result_label_df,result_df.name == result_label_df.name)
    result_df = change_column_datatype(result_df,"label",DoubleType)
    result_df.show()
    accuracy = evaluator.evaluate(result_df)
    print("Test Error = %g" % (1.0 - accuracy))
    """
    
    print("*************** Writing Output *******************")
    result.select("prediction","name").write.csv('gs://irene024082/output_MPC_large1/')
    
