#!/usr/bin/env python
# encoding: utf-8

# Definitions for ontology reasoning.
#
# https://github.com/stefanvanberkum/CD-ABSC
#
# Adapted from Trusca, Wassenberg, Frasincar and Dekker (2020).
# https://github.com/mtrusca/HAABSA_PLUS_PLUS
#
# Truşcǎ M.M., Wassenberg D., Frasincar F., Dekker R. (2020) A Hybrid Approach for Aspect-Based Sentiment Analysis Using
# Deep Contextual Word Embeddings and Hierarchical Attention. In: Bielikova M., Mikkonen T., Pautasso C. (eds) Web
# Engineering. ICWE 2020. Lecture Notes in Computer Science, vol 12128. Springer, Cham.
# https://doi.org/10.1007/978-3-030-50578-3_25

import nltk
import numpy as np
# noinspection PyUnresolvedReferences
import owlready2
from nltk import *
from nltk.parse.stanford import StanfordDependencyParser
from owlready2 import *

from config import *

nltk.download('averaged_perceptron_tagger')
nltk.download('wordnet')

# Path to the java runtime environment.
java_path = 'C:/Program Files/Java/jdk-14.0.1/bin/java.exe'
nltk.internals.config_java(java_path)
os.environ['JAVAHOME'] = java_path
owlready2.JAVA_EXE = java_path


class OntReasoner:
    """
    Ontology reasoner. Class obtained from Trusca et al. (2020), no original docstring provided.
    """

    def __init__(self):
        """
        Method obtained from Trusca et al. (2020), no original docstring provided.
        """
        onto_path.append("data/externalData")  # Path to ontology.
        ontologies = ["restaurant_manual.owl",   # 0
                      "restaurant_sasobus.owl",  # 1
                      "restaurant_soba.owl",     # 2
                      "finalPre.owl",            # 3
                      "finalPost.owl",           # 4
                      "restaurant_websoba.owl",  # 5
                      "finalT5.owl",             # 6
                      "finalRoberta.owl"]        # 7
        ontology_choice = 5
        self.onto = get_ontology(ontologies[ontology_choice])  # Name of ontology.
        print("Ontology: ", ontologies[ontology_choice])
        self.onto = self.onto.load()
        self.timeStart = time.time()
        self.classes = set(self.onto.classes())
        self.sencount = 0
        self.my_dict = {}

        self.remaining_sentence_vector = []
        self.remaining_target_vector = []
        self.remaining_polarity_vector = []
        self.remaining_pos_vector = []
        self.prediction_vector = []

        self.sentence_vector, self.target_vector, self.polarity_vector, self.polarity, self.posinfo = [], [], [], [], []

        self.majority_count = []

        for onto_class in self.classes:
            self.my_dict[onto_class] = onto_class.lex

    def predict_sentiment(self, sentence, target, onto, use_cabasc, use_svm, posinfo, types1, types2, types3):
        """
        Method obtained from Trusca et al. (2020), no original docstring provided.

        :param sentence:
        :param target:
        :param onto:
        :param use_cabasc:
        :param use_svm:
        :param posinfo:
        :param types1:
        :param types2:
        :param types3:
        :return:
        """
        words_in_sentence = sentence.split()
        self.sencount += 1

        target = target.strip()

        lemma_of_words_with_classes, words_with_classes, words_classes, target_class = self.get_class_of_words(
            words_in_sentence,
            target)

        positive_class = onto.search(iri='*Positive')[0]
        negative_class = onto.search(iri='*Negative')[0]

        found_positive_list = []
        found_negative_list = []

        for x in range(len(words_with_classes)):
            word = words_with_classes[x]
            lemma_of_word = lemma_of_words_with_classes[x]
            word_class = words_classes[x]
            negated = self.is_negated(word, words_in_sentence)

            if lemma_of_word in types1:
                found_positive, found_negative = self.get_sentiment_of_class(positive_class, negative_class, word_class,
                                                                             negated, False)
                found_positive_list.append(found_positive)
                found_negative_list.append(found_negative)

            if lemma_of_word in types2:
                if self.category_matches(target_class, word_class):
                    found_positive, found_negative = self.get_sentiment_of_class(positive_class, negative_class,
                                                                                 word_class, negated, False)

                    found_positive_list.append(found_positive)
                    found_negative_list.append(found_negative)

            if lemma_of_word in types3:
                if target_class is not None:
                    new_class = self.add_subclass(word_class, target_class)
                else:
                    new_class = word_class

                found_positive, found_negative = self.get_sentiment_of_class(positive_class, negative_class, new_class,
                                                                             negated, True)
                found_positive_list.append(found_positive)
                found_negative_list.append(found_negative)

        if True in found_positive_list and True not in found_negative_list:
            self.prediction_vector.append([1, 0, 0])

        elif True not in found_positive_list and True in found_negative_list:
            self.prediction_vector.append([0, 0, 1])
        # Create remaining vector for neural network.
        elif use_cabasc:
            self.sencount += -1
            self.polarity_vector = np.delete(self.polarity_vector, self.sencount, 0)
            self.remaining_sentence_vector.append(sentence)
            self.remaining_target_vector.append(target)
            self.remaining_pos_vector.extend((posinfo, posinfo + 1, posinfo + 2))
        # Create remaining vector for BoW model.
        elif use_svm:
            self.sencount += -1
            self.polarity_vector = np.delete(self.polarity_vector, self.sencount, 0)
            self.remaining_sentence_vector.append(sentence)
            self.remaining_target_vector.append(target)
            self.remaining_pos_vector.extend((int(posinfo / 3 * 4), int((posinfo / 3 * 4) + 1),
                                              int((posinfo / 3 * 4) + 2), int((posinfo / 3 * 4) + 3)))
        else:
            self.prediction_vector.append(self.get_majority_class(self.polarity_vector))
            self.majority_count.append(1)

    def get_class_of_words(self, words_in_sentence, target):
        """
        Method obtained from Trusca et al. (2020), no original docstring provided.

        :param words_in_sentence:
        :param target:
        :return:
        """
        self.classes = []
        words_with_classes = []
        lemma_of_words_with_classes = []
        wordnet_lemmatizer = WordNetLemmatizer()
        target_class = None

        for word in words_in_sentence:
            word_as_list = word_tokenize(word)

            ont_pos_tag = nltk.pos_tag(word_as_list)
            tag_only = ont_pos_tag[0][1]  # Get tag only.

            if tag_only.startswith('V'):  # Verb.
                lemma_of_word = wordnet_lemmatizer.lemmatize(word, 'v')
            elif tag_only.startswith('J'):  # Adjective.
                lemma_of_word = wordnet_lemmatizer.lemmatize(word, 'a')
            elif tag_only.startswith('R'):  # Adverb.
                lemma_of_word = wordnet_lemmatizer.lemmatize(word, 'r')
            else:  # Default is noun.
                lemma_of_word = wordnet_lemmatizer.lemmatize(word)

            for value in list(self.my_dict.values()):
                if lemma_of_word in value:
                    lemma_of_word_class = list(self.my_dict.keys())[list(self.my_dict.values()).index(value)]
                    self.classes.append(lemma_of_word_class)
                    lemma_of_words_with_classes.append(lemma_of_word)
                    words_with_classes.append(word)
                    if word == target:
                        target_class = lemma_of_word_class
                    break
        return lemma_of_words_with_classes, words_with_classes, self.classes, target_class

    def is_negated(self, word, words_in_sentence):
        """
        Method obtained from Trusca et al. (2020), no original docstring provided.

        :param word:
        :param words_in_sentence:
        :return:
        """
        # Negation check with window and dependency graph.
        path_to_jar = "C:/Users/jonat/anaconda3/envs/Thesis/code_main/stanford-parser-full-2018-02-27/stanford-parser.jar"
        path_to_models_jar = "C:/Users/jonat/anaconda3/envs/Thesis/code_main/stanford-english-corenlp-2018-02-27-models.jar"

        dependency_parser = StanfordDependencyParser(path_to_jar=path_to_jar, path_to_models_jar=path_to_models_jar)

        index = words_in_sentence.index(word)
        negated = False

        if index < 3:
            for i in range(index):
                temp = words_in_sentence[i]
                if "not" in temp or "n't" in temp or "never" in temp:
                    negated = True
        else:
            for i in range(index - 3, index):
                temp = words_in_sentence[i]
                if "not" in temp or "n't" in temp or "never" in temp:
                    negated = True
        negations = ["not", "n,t", "never"]
        if not negated and any(x in s for x in negations for s in words_in_sentence):
            result = dependency_parser.raw_parse(' '.join(words_in_sentence))
            dep = result.__next__()
            result = list(dep.triples())
            for triple in result:
                if triple[0][0] == word and triple[1] == 'neg':
                    negated = True
                    break
        return negated

    def get_sentiment_of_class(self, positive_class, negative_class, onto_class, negated, type3):
        """
        Method obtained from Trusca et al. (2020), no original docstring provided.

        :param positive_class:
        :param negative_class:
        :param onto_class:
        :param negated:
        :param type3:
        :return:
        """
        found_positive = False
        found_negative = False

        try:
            if type3:
                sync_reasoner()  # Run reasoner.
            found_positive = positive_class.__subclasscheck__(onto_class)
            if negated:
                found_positive = not found_positive
        except AttributeError:
            pass

        try:
            if type3:
                sync_reasoner()
            found_negative = negative_class.__subclasscheck__(onto_class)
            if negated:
                found_negative = not found_negative
        except AttributeError:
            pass
        return found_positive, found_negative

    def category_matches(self, target_class, onto_class):
        """
        Method obtained from Trusca et al. (2020), no original docstring provided.

        :param target_class:
        :param onto_class:
        :return:
        """
        if target_class is None:
            return False

        target_ancestors = target_class.ancestors()
        target_mentions = []
        for target_an in target_ancestors:
            name = target_an.__name__
            if "Mention" in name:
                target_mentions.append(name.rsplit('Mention', 1)[0])

        onto_ancestors = onto_class.ancestors()
        onto_mentions = []
        for onto_an in onto_ancestors:
            name = onto_an.__name__
            if "Mention" in name:
                onto_mentions.append(name.rsplit('Mention', 1)[0])

        common_list = list(set(target_mentions).intersection(set(onto_mentions)))
        if len(common_list) > 2:  # If they have more than 2 ancestors in common.
            return True
        else:
            return False

    def add_subclass(self, onto_class, target_class):  # Add new subclass to ontology.
        """
        Method obtained from Trusca et al. (2020), no original docstring provided.

        :param onto_class:
        :param target_class:
        :return:
        """
        onto_name = onto_class.__name__
        target_name = target_class.__name__
        new_class = types.new_class(onto_name + target_name, (onto_class, target_class))
        return new_class

    def get_majority_class(self, polarity_vector):
        """
        Method obtained from Trusca et al. (2020), no original docstring provided.

        :param polarity_vector:
        :return:
        """
        total = polarity_vector.sum(0)
        index = np.argmax(total)
        if index == 0:
            return [1, 0, 0]
        elif index == 1:
            return [0, 1, 0]
        else:
            return [0, 0, 1]

    def create_types(self):
        """
        Method obtained from Trusca et al. (2020), no original docstring provided.

        :return:
        """
        types1 = set()
        types2 = set()
        types3 = set()

        classes = list(self.onto.classes())

        for c in classes:
            name_class = c.__name__
            remove_words = ['Property', "Mention", "Positive", "Neutral", "Negative"]
            if any(word in name_class for word in remove_words):
                continue
            ancestors = c.ancestors()
            boolean = 1
            ancestors_list = []
            for an in ancestors:
                name_an = an.__name__
                ancestors_list.append(name_an)
            ancestors_list.sort()

            for name_ancestor in ancestors_list:
                if boolean == 1:
                    if "Generic" in name_ancestor:
                        types1.add(name_class.lower())
                        boolean = 0
                    elif "Positive" in name_ancestor or "Negative" in name_ancestor:
                        types2.add(name_class.lower())
                        boolean = 0
                    elif "PropertyMention" in name_ancestor:
                        types3.add(name_class.lower())
                        boolean = 0
        return types1, types2, types3

    def run(self, use_backup, path, use_svm, cross_val=False, j=0):
        """
        Method obtained from Trusca et al. (2020), no original docstring provided.

        :param use_backup:
        :param path:
        :param use_svm:
        :param cross_val:
        :param j:
        :return:
        """
        types1, types2, types3 = self.create_types()

        punctuation_and_numbers = ['– ', '_', '(', ')', '?', ':', ';', ',', '.', '!', '/', '"', '\'', '’', '*', '$',
                                   '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
        with open(path, "r") as fd:
            lines = fd.read().splitlines()
            for i in range(0, len(lines), 3):
                # Polarity.
                if lines[i + 2].strip().split()[0] == '-1':
                    self.polarity_vector.append([0, 0, 1])
                elif lines[i + 2].strip().split()[0] == '0':
                    self.polarity_vector.append([0, 1, 0])
                elif lines[i + 2].strip().split()[0] == '1':
                    self.polarity_vector.append([1, 0, 0])

                # Load target and sentence.
                words_tar = lines[i + 1].lower()
                words = lines[i].lower()
                words = words.replace('$t$', words_tar)
                # Remove punctuation.
                for _ in punctuation_and_numbers:
                    words_tar = words_tar.replace(_, '')
                for _ in punctuation_and_numbers:
                    words = words.replace(_, '')

                self.target_vector.append(words_tar)
                self.sentence_vector.append(words)
                self.posinfo.append(i)

        self.sentence_vector = np.array(self.sentence_vector)
        self.target_vector = np.array(self.target_vector)
        self.polarity_vector = np.array(self.polarity_vector)
        self.posinfo = np.array(self.posinfo)

        for x in range(len(self.sentence_vector)):  # For each sentence
            print("Sentence " + str(x + 1) + " out of " + str(len(self.sentence_vector)))
            self.predict_sentiment(self.sentence_vector[x], self.target_vector[x], self.onto, use_backup, use_svm,
                                   self.posinfo[x], types1, types2, types3)

        self.prediction_vector = np.array(self.prediction_vector)
        argmax_pol = np.argmax(self.polarity_vector, axis=1)
        argmax_pred = np.argmax(self.prediction_vector, axis=1)
        bool_vector = np.equal(argmax_pol, argmax_pred)
        int_vec = bool_vector.astype(float)

        ont_accuracy = sum(int_vec) / (self.sentence_vector.size - len(self.remaining_sentence_vector))

        time_end = time.time()

        print("Accuracy: ", ont_accuracy)
        print('Runtime: ', (time_end - self.timeStart))
        print('Majority: ', len(self.majority_count))

        # Convert to numpy array to save the output.
        self.remaining_sentence_vector = np.array(self.remaining_sentence_vector)
        self.remaining_target_vector = np.array(self.remaining_target_vector)
        self.remaining_polarity_vector = np.array(self.remaining_polarity_vector)
        self.remaining_pos_vector = np.array(self.remaining_pos_vector)

        # Save the outputs to .txt file.
        if use_backup:
            out_f = open(FLAGS.remaining_test_path, "w")
            with open(FLAGS.test_path, "r") as fd:
                for i, line in enumerate(fd):
                    if i in self.remaining_pos_vector:
                        out_f.write(line)
            out_f.close()
        if use_svm:
            out_f = open(FLAGS.remaining_svm_test_path, "w")
            with open(FLAGS.test_svm_path, "r") as fd:
                for i, line in enumerate(fd):
                    if i in self.remaining_pos_vector:
                        out_f.write(line)

        if cross_val:
            if use_backup:
                out_f = open(
                    "data/programGeneratedData/crossValidation" + str(FLAGS.year) + '/cross_val_remainder_' + str(
                        j + 1) + '.txt', "w")
                with open(FLAGS.test_path, "r") as fd:
                    for i, line in enumerate(fd):
                        if i in self.remaining_pos_vector:
                            out_f.write(line)
                out_f.close()
            if use_svm:
                out_f = open(
                    "data/programGeneratedData/crossValidation" + str(FLAGS.year) + '/svm/cross_val_remainder_' + str(
                        j) + '.txt', "w")
                with open(FLAGS.test_svm_path, "r") as fd:
                    for i, line in enumerate(fd):
                        if i in self.remaining_pos_vector:
                            out_f.write(line)

        return ont_accuracy, len(self.remaining_pos_vector) / 3
