import argparse
import re
import numpy as np
from operator import add

from pyspark import SparkContext
from pyspark.ml.feature import NGram
from pyspark.sql import SparkSession

from pyspark.ml.linalg import Vectors
from pyspark.ml.feature import StringIndexer
from pyspark.ml.classification import RandomForestClassifier

from pyspark.sql.types import *

BYTES_PATTERN = re.compile(r'\s([A-F0-9]{2})\s')
SEGMENT_PATTERN = re.compile(r'([a-zA-Z]+):[a-zA-Z0-9]{8}[\t\s]')
OPCODE_PATTERN = re.compile(r'([\s])([A-F0-9]{2})([\s]+)([a-z]+)([\s+])')


def preprocess(data_folder_path, filenames, type):
    myRDDlist = []
    for filename in filenames:
        new_rdd = sc.textFile(data_folder_path +"/"+ filename + type).map(lambda x: (filename,x)).groupByKey().map(lambda x: (x[0],' '.join(x[1])))
        myRDDlist.append(new_rdd)
    Spark_Full = sc.union(myRDDlist)
    return Spark_Full

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

def extract_features(file_rdd, feature_name):
    """
        This function extracts the required features
        
        --input-------------------------------------
        file_rdd : [(<hash1>, <content1>), ...]
        feature_name : str
        
        --output------------------------------------
        filename_label_pair : [(<hash1>,<feature1>), (<hash1>,<feature2>), ..., (<hashN>,<featureK>)]
    """
    
    if feature_name=='bytes':
        return file_rdd.map(lambda x: (x[0],BYTES_PATTERN.findall(x[1]))).flatMapValues(lambda x:x)
    elif feature_name=='segment':
        return file_rdd.map(lambda x: (x[0],SEGMENT_PATTERN.findall(x[1]))).flatMapValues(lambda x:x)
    elif feature_name=='opcode':
        return file_rdd.map(lambda x: (x[0],OPCODE_PATTERN.findall(x[1]))).flatMapValues(lambda x:x).map(lambda x: (x[0],x[1][3]))
    else:
        return "Invalid input!"

def Ngram(feature_rdd,start,end):
    '''
        --input-------------------------------------
        feature_rdd : [(<hash1>,<feature1>), (<hash1>,<feature2>), ..., (<hashN>,<featureK>)]
        
        --output------------------------------------
        Ngram_count : [((<hash>,<ngram feature>),cnt), ...]
        '''
    Ngram_list = []
    for i in range(start,end):
        Ngram_list.append(Ngram_feature(i, feature_rdd))
    Ngram_count = sc.union(Ngram_list)
    return Ngram_count

def Ngram_feature(N, feature_rdd):
    '''
        Extract and count N-gram. Leave top 1000 n-gram features if it's 2-gram or more.
        
        Input:
        feature_rdd : [(<hash1>,<feature1>), (<hash1>,<feature2>), ..., (<hashN>,<featureK>)]
        
        Output:
        freq_ngram_count_rdd : [((<hash>,<ngram feature>),cnt), ...]
        '''
    feature_rdd = feature_rdd.groupByKey().map(lambda x: (x[0],list(x[1])))
    df = spark.createDataFrame(feature_rdd).toDF("file_names", "features")
    ngram = NGram(n=N, inputCol="features", outputCol="ngrams")
    ngramDataFrame = ngram.transform(df)
    ngram_rdd = ngramDataFrame.rdd.map(tuple).map(lambda x: (x[0],x[2])).flatMapValues(lambda x: x)
    ngram_count_rdd = ngram_rdd.map(lambda x: ((x),1)).reduceByKey(add)
    freq_ngram_count_rdd = ngram_count_rdd

    if not N == 1:
        #[(<ngram feature>,cnt), ...]
        topN_ngram_count_rdd = freq_ngram_count_rdd.map(lambda x: (x[0][1],x[1])).reduceByKey(add)
        #[((<ngram feature>,cnt),index), ...]
        topN_ngram_count_rdd = topN_ngram_count_rdd.sortBy(lambda x: x[1],ascending=False).zipWithIndex()
        length = topN_ngram_count_rdd.count()
        #top [(<ngram feature>,cntSum), ...]
        topN_ngram_count_rdd = topN_ngram_count_rdd.filter(lambda x: x[1]<1000).map(lambda x: x[0])
        #freq [(<ngram feature>,(<hash>,cnt)), ...]
        freq_ngram_count_rdd = freq_ngram_count_rdd.map(lambda x: (x[0][1],(x[0][0],x[1])))
        #[(<ngram feature>,(cntSum,(<hash>,cnt))), ...]
        freq_ngram_count_rdd = topN_ngram_count_rdd.join(freq_ngram_count_rdd).map(lambda x: ((x[1][1][0],x[0]),x[1][1][1]))
    
    return freq_ngram_count_rdd

def build_full_feature_list(features,length):
    '''
        Build a full feature list using numpy array (very fast)
        '''
    full_feature_narray = np.zeros(length,)
    full_feature_narray[features[:,0]] = features[:,1]
    return full_feature_narray


def test_RF_structure(all_test_features_count,distinct_features_rdd):
    '''
        Build the data structure used for testing data
        Leave only features that already appear in training
        
        Input:
        all_test_features_count : [(<ngram feature>,(<hash>,cnt)), ...]
        distinct_features_rdd : [(<ngram feature>,index), ...]
        
        Output:
        all_test_features_count : [(<ngram feature>,((<hash>,cnt),index)), ...]
        '''
    #--[(<ngram feature>,(<hash>,cnt)), ...]-----------------------------------------
    all_test_features_count = all_test_features_count.map(lambda x: (x[0][1],(x[0][0],x[1])))

    #--[(<ngram feature>,(index,(<hash>,cnt))), ...]-----------------------------------------
    all_test_features_count = all_test_features_count.leftOuterJoin(distinct_features_rdd).filter(lambda x: not x[1][1]==None)

    #--[(<hash>,(index,cnt)), ...]-------------------------------------------------------
    full_features_index_count_rdd = all_test_features_count.map(lambda x: (x[1][0][0],(x[1][1],x[1][0][1]))).groupByKey().map(lambda x: (x[0],np.asarray(list(x[1]),dtype=int)))

    length = distinct_features_rdd.count()
    #--[(<hash>,[cnt1, cnt2, ...]]), ...]-------------------------------------------------------
    full_test_feature_count_rdd = full_features_index_count_rdd.map(lambda x: (x[0],Vectors.dense(list(build_full_feature_list(x[1],length)))))
    
    test_rdd = full_test_feature_count_rdd.map(lambda x: len(list(x[1])))
    
    return full_test_feature_count_rdd


def RF_structure(all_features_count):
    '''
        Build the data structure used for training data
        
        Input:
        all_features_count : [((<hash>,<ngram feature>),cnt), ...]
        
        Output:
        full_feature_count_rdd : [((<hash1>,<label1>),[cnt1,cnt2,...]), ...]
        '''
    #--[(<ngram feature>,index), ...]------------------------------------------------
    distinct_features_rdd = all_features_count.map(lambda x: x[0][1]).distinct().zipWithIndex()
    length = distinct_features_rdd.count()

    #--[(<ngram feature>,(<hash>,cnt)), ...]-----------------------------------------
    all_features_count_rdd = all_features_count.map(lambda x: (x[0][1],(x[0][0],x[1])))

    #--[(<hash>,(index,cnt)), ...]---------------------------------------------------
    feature_id_count_rdd = distinct_features_rdd.join(all_features_count_rdd).map(lambda x: (x[1][1][0],(x[1][0],x[1][1][1])))

    #--[(<hash>,[(index,cnt), ...]), ...]--------------------------------------------
    feature_id_count_rdd = feature_id_count_rdd.groupByKey().map(lambda x: (x[0],np.asarray(list(x[1]),dtype=int)))

    #--[(<hash>,DenseVector([cnt1,cnt2,...])), ...]-----------------------------------------------
    full_feature_count_rdd = feature_id_count_rdd.map(lambda x: (x[0], Vectors.dense(list(build_full_feature_list(x[1],length)))))

    test_rdd = full_feature_count_rdd.map(lambda x: len(list(x[1])))

    return full_feature_count_rdd, distinct_features_rdd

def create_indexed_df(full_train_feature_rdd):
    '''
        input: [(<hash1>,label1,[cnt1,cnt2,...]), ...]
        '''
    df = spark.createDataFrame(full_train_feature_rdd).toDF("name","label", "features")
    
    stringIndexer = StringIndexer(inputCol="name", outputCol="indexed")
    si_model = stringIndexer.fit(df)
    indexed_df = si_model.transform(df)
    indexed_df.show()
    return indexed_df

def RF(indexed_df):
    RF_model = RandomForestClassifier(numTrees=50, maxDepth=25, labelCol="label")
    td_new = change_column_datatype(indexed_df,"label",DoubleType)
    model = RF_model.fit(td_new)
    return model

def change_column_datatype(td,col_name,datatype):
    td_new = td.withColumn(col_name, td[col_name].cast(datatype()))
    return td_new


if __name__ == "__main__":

    sc = SparkContext()
    spark = SparkSession.builder.master("yarn").appName("Word Count").config("spark.some.config.option", "some-value").getOrCreate()

    parser = argparse.ArgumentParser(description = "CSCI 8360 Project 2",
                                     epilog = "answer key", add_help = "How to use",
                                     prog = "python p2.py [asm_folder_path] [bytes_folder_path] [training_file] [training_label] [testing_file] [output_path]")
    # Required args
    parser.add_argument("paths", nargs=6,
                        help = "Paths of asm_folder, bytes_folder, training_data, training_labels, and testing-data.")

    # Optional args
    parser.add_argument("-t", "--testing_label", default = None, help = "path of testing label")

    args = vars(parser.parse_args())

    data_asm_folder_path = args['paths'][0]
    data_bytes_folder_path = args['paths'][1]
    
    training_file_names = args['paths'][2]
    training_label = args['paths'][3]
    test_file_names = args['paths'][4]
    output_path = args['paths'][5]
    test_label = args['testing_label']

    #---Read in the data names and labels------------------------------------------
    train_filenames_rdd = sc.textFile(training_file_names)
    train_filenames_list = train_filenames_rdd.collect()
    train_labels_rdd = sc.textFile(training_label)
    
    test_filenames_rdd =sc.textFile(test_file_names)
    test_filenames_list = test_filenames_rdd.collect()
    test_labels_rdd = sc.textFile(test_label)

    #---Read in actual bytes/asm files---------------------------------------------
    #---format: [(<hash1>,<content1>),(<hash2>,<content2>), ...]-------------------
    train_asm_file_rdd = preprocess(data_asm_folder_path, train_filenames_list,".asm")
#    train_byte_file_rdd = preprocess(data_bytes_folder_path, train_filenames_list,".bytes")

    test_asm_file_rdd = preprocess(data_asm_folder_path, test_filenames_list,".asm")
#    test_byte_file_rdd = preprocess(data_bytes_folder_path, test_filenames_list,".bytes")

    #---Create a label+filename pair-------------------------------------------------------
    #---output: [(<hash1>,<label1>), (<hash2>,<label2>), ...]------------------------------
    filename_label_pair_rdd = get_filename_label_pair(train_filenames_rdd, train_labels_rdd)
    
    #---Extract the feaures----------------------------------------------------------------
    #---output: [(<hash1>,<feature1>), (<hash1>,<feature2>), ..., (<hashN>,<featureK>)]----
#    train_bytes_rdd = extract_features(train_byte_file_rdd, 'bytes')
    train_segment_rdd = extract_features(train_asm_file_rdd, 'segment')
#    train_opcode_rdd = extract_features(train_asm_file_rdd, 'opcode')

#    test_bytes_rdd = extract_features(test_byte_file_rdd, 'bytes')
    test_segment_rdd = extract_features(test_asm_file_rdd, 'segment')
#    test_opcode_rdd = extract_features(test_asm_file_rdd, 'opcode')

    #---Find N gram of the features------------------------------------------------
    #---output: [((<hash>,<ngram feature>),cnt), ...]------------------------------
#    train_Ngram_bytes_rdd = Ngram(train_bytes_rdd,1,2)
    train_Segment_rdd = Ngram(train_segment_rdd,1,2)
#    train_Ngram_opcode_rdd = Ngram(train_opcode_rdd,4,5)

#    test_Ngram_bytes_rdd = Ngram(test_bytes_rdd,1,2)
    test_Segment_rdd = Ngram(test_segment_rdd,1,2)
#    test_Ngram_opcode_rdd = Ngram(test_opcode_rdd,4,5)

    all_train_features_count = train_Segment_rdd#.union(train_Ngram_bytes_rdd)
    all_test_features_count = test_Segment_rdd#.union(test_Ngram_bytes_rdd)

    #---Pre Random Forest(Prepare for the data structure)----------------------------
    #---[(<hash1>,[cnt1,cnt2,...]), ...]---------------------------------------------
    full_train_feature_rdd, distinct_features_rdd = RF_structure(all_train_features_count)
    full_test_feature_rdd = test_RF_structure(all_test_features_count,distinct_features_rdd)

    #---Link label in----------------------------------------------------------------
    #---output: [(<hash1>,label1,[cnt1,cnt2,...]), ...]------------------------------
    full_train_feature_rdd = filename_label_pair_rdd.join(full_train_feature_rdd).map(lambda x: (x[0],x[1][0],x[1][1]))
    
    #---Create Dataframe for training------------------------------------------------
    feature_label_full_df = create_indexed_df(full_train_feature_rdd)
    
    #---Training Random Forest Model-------------------------------------------------
    training_model = RF(feature_label_full_df)
    
    #---Create dataframe for testing-------------------------------------------------
    test_feature_df = spark.createDataFrame(full_test_feature_rdd).toDF("name","features")
    stringIndexer = StringIndexer(inputCol="name", outputCol="indexed")
    test_model = stringIndexer.fit(test_feature_df)
    test_feature_indexed_df = test_model.transform(test_feature_df)
    

    #---Prediction--------------------------------------------------------------------
    result = training_model.transform(test_feature_indexed_df)
    result = result.withColumn("prediction", result["prediction"].cast("int"))
    result.show()
    result = result.select("prediction","name")

    #---Write to Bucket---------------------------------------------------------------
    rdd = result.rdd.map(tuple).map(lambda x: (x[1],x[0]))
    test_file_names = test_filenames_rdd.zipWithIndex()
    predict_rdd = rdd.join(test_file_names).sortBy(lambda x: x[1][1]).map(lambda x:x[1][0])
    pre = spark.createDataFrame(predict_rdd.map(lambda x: ('prediction',x))).toDF("name","prediction")
    pre_repa = pre.repartition(1)
    tosavedf = pre_repa.select("prediction").write.csv(test_label)


    #---Print Result if testing labels are given-------------------------------------
    if not test_label == None:
        predict = predict_rdd.collect()
        test_rdd_label = test_labels_rdd.collect()
        score = 0.0
        for i in range(len(predict)):
            predict[i] = str(predict[i])
            if predict[i] == test_rdd_label[i]:
                score +=1.0
        accuracy = score*100/len(predict)
        print("Accuracy: "+str(accuracy)+"%")




















