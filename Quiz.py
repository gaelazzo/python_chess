
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
from LearningBase import LearningBase, LearnPosition
import json_helper

folder = "data"

def getLearningBaseClassified(learningBase: LearningBase) -> List[tuple[str, Dict[str, int]]]:
    # evaluates statistics about ECO classification
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
          
    sortedEcoStats = getLearningBaseClassified(learningBase)

    for eco,stats in sortedEcoStats:
        print(f"ECO {eco}: {stats['distinct']} distinct  {stats['total']} total, {stats['ok']} ok, {stats['bad']} bad ")
    
def makeQuizzes(learningBase:LearningBase):
    quiz_size = 10
    curr_quiz_size = 0
    sortedEcoStats = getLearningBaseClassified(learningBase)

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

def nameQuizzes(learningBase:LearningBase)->Dict[int,str]:
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
    
              
def classifyLearningBase(learningBase:LearningBase):
    '''
    Classify the learning base by ECO code
    '''
    print(f"Classifying {learningBase.filename} with {len(learningBase.positions)} positions")
    makeQuizzes(learningBase)
    quizNames = nameQuizzes(learningBase)
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
            print(f"File {fname} already classified")
            continue
        classifyLearningBase(learnBase)

print(f"Start classifying bases")
classifyAllLearningBases()
print(f"Classification Done")
