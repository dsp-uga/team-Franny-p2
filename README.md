# team-Franny-p2

# Project 2: Malware Classification

This project is a problem of Malware classification given asm and bytes files of malware from one of 9 classes. Each class is labeled as number between 1 to 9. 

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

- [Python 3.6](https://www.python.org/downloads/release/python-360/)
- [Apache Spark 2.2.1](http://spark.apache.org/)
- [Pyspark 2.2.1](https://pypi.python.org/pypi/pyspark/2.2.1) - Python API for Apache Spark
- [Google Cloud Platform](https://cloud.google.com) - File is extremely large so cloud computing is essential
- [Anaconda](https://www.anaconda.com/) - packages manager for [nltk](http://www.nltk.org/), [string](https://docs.python.org/3/library/string.html)

### Environment Setup
### Anaconda

Anaconda is a complete Python distribution embarking automatically the most common packages, and allowing an easy installation of new packages.

Download and install Anaconda (https://www.continuum.io/downloads).

The `environment.yml` file for conda is placed in [Extra](https://github.com/dsp-uga/team-andromeda-p1/tree/master/Extra) for your ease of installation

### Spark

Download the latest, pre-built for Hadoop 2.6, version of Spark.
* Go to http://spark.apache.org/downloads.html
* Choose a release (prendre la dernière)
* Choose a package type: Pre-built for Hadoop 2.6 and later
* Choose a download type: Direct Download
* Click on the link in Step 4
* Once downloaded, unzip the file and place it in a directory of your choice

Go to [WIKI](https://github.com/dsp-uga/team-andromeda-p1/wiki) tab for more details of running IDE for Pyspark. ([IDE Setting for Pyspark](https://github.com/dsp-uga/team-andromeda-p1/wiki/IDE-Setting-for-Pyspark))

## Running the tests

You can run `p2.py` via regular **python** or run the script via **spark-submit**. You should specify the path to your spark-submit.

```
$ python p2.py
```
```
$ usr/bin/spark-submit p2.py 
```

If you want to run it on GCP through your local terminal, you can submit a job using dataproc.

```
gcloud dataproc jobs submit pyspark path/to/team-Franny-p2/p2.py --cluster = your-cluster-name
```

The output prediction will be saved to your GCP Bucket with the path you provided.

### Packages Used

#### Ngram from pyspark.ml.feature

```
from pyspark.ml.feature import NGram
```

NGram from pyspark.ml package is used to extract the Ngram features given tokenized bytes or opcodes. It requires to convert rdd data to dataframe for the process with a column containing all the tokenized features in on list. Order of these features is required to be the same as they are in the file.

#### RandomForestClassifier from pyspark.ml.classification

```
from pyspark.ml.classification import RandomForestClassifier
```

RandomForestClassifier is used for modeling and making predictions for this problem. The concept of Random Forest classification is explained in [WIKI]()

### Overview

This projects mainly uses [Random Forest classifier]() with several preprcessing methods. Here's the brief flow to explain the code:

1. Bytes tokenizing by regular expression `r'\s([A-F0-9]{2})\s` that matches two hexadecimal pairs with space in both end.
2. Ngram Bytes feature construction. Here in the final code, we used 1 and 2 gram bytes.
3. Get the most frequent features to prevent overfitting and memory issue. We kept all 256 1-gram bytes and the most frequent 1000 2-gram bytes in the end.
4. Construct the data structure for RandomForestClassifier. The final data structure before converting into data frame is `[(<hash1>,label1,[cnt1,cnt2,...]), ...]`
5. Random Forest Classification.

#### Experiment on Features:

During our implementation, we tried to use different features and different combinations of several features for training the model. Here are the features that we extracted. Results of different combinations are shown in [Result section](). 

* **Segment** 

First token of each line in asm files such as `HEADER, text, data, rsrc, CODE` etc.

* **Byte** 

Hexadecimal pairs in bytes files.

* **Opcode** 

Opcodes in asm files such as `cmp, jz, mov, sub` etc.

#### Experiment on Dimension Reduction:

Since the files are large, features extracted from them are extremely large. Therefore, feature dimension reduction is essential to prevent from overfitting and also reduce the processing time.

* **IDF** 

We tried setting IDF threshold to filter out some "less meaningful" opcodes. Since opcodes are for specifying what to do in assembly language, it seems reasonable to check whether this opcode is special to this file meaning or it's a opcode that appears commonly across all files (similar to stopwords).

* **Or simply filter out less frequency features** 

#### Feature Selection

## Result

We tried several feature extractions to see which one performs best (we only have one result on large set): 

|Features                              |Accuracy on Small|Accuracy on Large|Tree Numb|Tree Depth|
|--------------------------------------|-----------------|-----------------|---------|----------|
|segment                               |  %              |  %              |         |          |
|1-gram Bytes                          |  %              |       N/A       |         |          |
|1-gram & 2-gram Bytes                 |86%              |  %              |         |          |
|segment & 1-gram bytes                |  %              |       N/A       |         |          |
|segment & 1-gram & 2-gram Bytes       |  %              |       N/A       |         |          |
|1-gram & 2-gram opcodes               |  %              |       N/A       |         |          |
|segment & 1-gram & 2-gram opcodes     |  %              |       N/A       |         |          |
|segment & 4-gram opcodes              |  %              |       N/A       |         |          |

## Contributing

Please read [CONTRIBUTING.md](https://gist.github.com/PurpleBooth/b24679402957c63ec426) for details on our code of conduct, and the process for submitting pull requests to us.

## Authors

* **Aishwarya Jagtap** - 
* **Ailing Wang** - 
* **Weiwen Xu** - [WeiwenXu21](https://github.com/WeiwenXu21)

See also the list of [contributors](https://github.com/your/project/contributors) who participated in this project.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
