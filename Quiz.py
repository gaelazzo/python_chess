
from __future__ import annotations 
from argparse import OPTIONAL
from operator import le
import os
# [m for m in g.mainline_moves()]
import chess
import chess.pgn
import chess.polyglot
from typing import Optional,List,Dict,Tuple,Dict
from LearningBase import LearnPosition, LearningBase, learningBases
from datetime import datetime, timedelta, date
import csv
from LearningBase import LearningBase, LearnPosition, DATA_FOLDER
import json_helper

folder = DATA_FOLDER

def getLearningBaseClassified(learningBase: LearningBase) -> List[tuple[str, Dict[str, int]]]:
    '''
    evaluates statistics on the learningBase splitting on ECO classification
    '''

    ecoStats:Dict[str,Dict[str,int]] = {}
    for pos in learningBase.positions.values():
        eco = pos.eco
        if eco not in ecoStats:
            ecoStats[eco] = {"ok":0, "bad":0, "total": 0, "distinct":0}
        stats = ecoStats[eco]
        stats["ok"] += pos.successful
        stats["bad"] += pos.ntry - pos.successful
        stats["total"] += pos.ntry  
        stats["distinct"] += 1 

    # Ordina le classificazioni ECO per frequenza (numero totale di posizioni)
    sortedEcoStats = sorted(ecoStats.items(), key=lambda item: item[1]["distinct"], reverse=True)
    return sortedEcoStats



def describeLearningBase(learningBase:LearningBase):    
    '''
    Prints a summary of the learning base statistics
    '''
    sortedEcoStats = getLearningBaseClassified(learningBase)

    for eco,stats in sortedEcoStats:
        print(f"ECO {eco}: {stats['distinct']} distinct  {stats['total']} total, {stats['ok']} ok, {stats['bad']} bad ")
    



def _makeQuizzes_by_eco(learningBase:LearningBase, quiz_size:int=5):
    '''
    Create quizzes grouping positions by ECO. If a learning base has already quizzes assigned, it will not change them.
    '''
    print(f"Classifying {learningBase.filename} with {len(learningBase.positions)} positions")

    curr_quiz_size = 0
    sortedEcoStats = getLearningBaseClassified(learningBase)
    
    # id del massimo quiz presente nella learning base
    max_id_quiz=0
    for pos in learningBase.positions.values():
        if pos.idquiz is None:
            continue
        if pos.idquiz > max_id_quiz:
            max_id_quiz = pos.idquiz
    
    max_id_quiz += 1

    for eco, stats in sortedEcoStats:
        positions = [ pos for pos in learningBase.positions.values() if pos.eco == eco and  pos.idquiz is None]        
        for pos in positions:
            pos.idquiz = max_id_quiz
            curr_quiz_size += 1
            if curr_quiz_size >= quiz_size:
                max_id_quiz += 1
                curr_quiz_size = 0

def name_unnamed_Quizzes(existingQuizzesName:Dict[str,str], learningBase:LearningBase, lessonName:str)->Dict[int,str]:
    '''
        Assign a name to each unnamed quiz 
        Arguments:
            learningBase: The learning base to classify
            lessonName: The name to assign to unnamed quizzes
        Returns:
            A dictionary with the quiz id as key and the quiz name as value.
    '''

    quizzes:Dict[int, List[LearnPosition]] = {}
    for pos in learningBase.positions.values():
        if not int(pos.idquiz) in quizzes:
            quizzes[pos.idquiz]= []
        quizzes[pos.idquiz].append(pos)  # assign the position to the quiz in the dictionary quizzes 
    
    for idquiz, base in quizzes.items():
        if not (idquiz in existingQuizzesName):
            existingQuizzesName[idquiz] = lessonName  # Default name for the quiz
    
    return existingQuizzesName

def nameQuizzes_by_eco(learningBase:LearningBase)->Dict[int,str]:
    '''
        Assign a name to each quiz based on the ECO code of the positions in the quiz
        If the quiz contains positions with the same ECO code, it will use that code as the name.
        If the quiz contains positions with two different ECO codes, it will use both codes separated by a space.
        If the quiz contains positions with more than two different ECO codes, it will use 'mix' as the name.
        Arguments:
            learningBase: The learning base to classify
        Returns:
            A dictionary with the quiz id as key and the quiz name as value.
    '''

    quizzes:Dict[int, List[LearnPosition]] = {}
    quizzesName:Dict[int,str] = {}
    for pos in learningBase.positions.values():
        if not pos.idquiz in quizzes:
            quizzes[pos.idquiz]= []
        quizzes[pos.idquiz].append(pos)
    
    for idquiz, base in quizzes.items():
        eco:set[str] = set()
        for learnPos in base:
            eco.add(learnPos.eco)
        
        if len(eco) == 1:
            quizzesName[idquiz] = next(iter(eco))  # L'unico elemento in eco
        elif len(eco) == 2:
            quizzesName[idquiz] = ' '.join(eco)  # I due elementi in eco
        else:
            quizzesName[idquiz] = 'mix'  # Più di due elementi 
    
    return quizzesName
    



def assign_unnamed_quizzes(quizzes:dict[str,str], learningBase:LearningBase, lessonName:str): 
    '''
        Merge all lessons from a PGN file to a given learning base.
        Args:
            quizzes: A dictionary with the quiz id as key and the quiz name as value.
            learningBase: The learning base to examine
            colorToAnalyze: True for white/ False for black
    '''
    _makeQuizzes_by_eco(learningBase)   
    name_unnamed_Quizzes(quizzes, learningBase, lessonName)        
    json_helper.write_struct(os.path.join(folder,f"lessons_{learningBase.filename}.json"), quizzes)
    learningBase.save()


#was classifyLearningBase              
def makeQuizzes_by_ECO(learningBase:LearningBase):
    '''
    Create quizzes grouping positions by ECO classification
    '''    
    _makeQuizzes_by_eco(learningBase)
    quizNames = nameQuizzes_by_eco(learningBase)
    json_helper.write_struct(os.path.join(folder,f"lessons_{learningBase.filename}.json"), quizNames)
    learningBase.save()

def classifyAllLearningBases():
    '''
    Classify all learning bases
    '''
    for name, learnBase in learningBases.items():
        # check if file already exists
        fname = os.path.join(folder, f"lessons_{name}.json")
        if os.path.exists(fname):
            #print(f"File {fname} already classified")
            continue
        makeQuizzes_by_ECO(learnBase)

#print(f"Start classifying bases")
classifyAllLearningBases()
#print(f"Classification Done")
