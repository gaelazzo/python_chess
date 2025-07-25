import requests
import json_helper
import os
import LearningBase
from datetime import datetime
from dataclasses import dataclass,fields
from typing import Optional, Union,List,Dict, Tuple, Iterator, Any
import json
from config import config
import sys

def get_base_path():
    """Restituisce il percorso della cartella dove si trova l'eseguibile o lo script"""
    if getattr(sys, 'frozen', False):  # Se è un eseguibile PyInstaller
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
DATA_FOLDER = os.path.join(BASE_PATH, "data")

# Nome del file di configurazione


# URL del tuo servizio Flask
#base_url = 'http://localhost:5000/api/'
#id_student = 'gaetano.lazzo'


def create_course(id_course:str):
    '''
    Create a course in the Brain Master service.
    Args:
        id_course(str): unique identifier for the course, e.g. 'openings', 'C42_white', etc.
    '''
    url = f"{config.base_url}create_course"
    payload = {
            'id_course': id_course,
            'description': 'Chess course'
        }
    
    try:        
        response = requests.post(url, json=payload)
    
        # Controllo del risultato
        if response.status_code == 200:
            print('Corso creato con successo!')
            print('Risposta:', response.json())  # Se restituisci un JSON dal backend
        else:
            print('Errore:', response.status_code, response.text)
    except Exception as e:
        print('Errore nella richiesta:', str(e))
    
def create_lesson(id_lesson:str, id_course:str, title:str, description:str):
    '''
    Create a lesson in the Brain Master service.
    Args:
        id_lesson(str): unique identifier for the lesson, e.g. 'C44_black', 'C42_white', etc.
        id_course(str): unique identifier for the course
        title(str): title of the lesson
        description(str): description of the lesson
    '''
    url = f'{config.base_url}create_lesson'
    payload = {
        'id_lesson': id_lesson,
        'id_course': id_course,
        'title': title,
        'description': description
    }

    try:
        response = requests.post(url, json=payload)
    
        # Controllo del risultato
        if response.status_code == 200:
            print(f'Lezione {id_lesson} creata con successo!')
            print('Risposta:', response.json())  # Se restituisci un JSON dal backend
        else:
            print('Errore:', response.status_code, response.text)
    except Exception as e:
        print('Errore nella richiesta:', str(e))

def add_question(id_course:str, id_test:str, id_lesson:str, id_question:str,
                        lesson_name:str, lesson_descr:str,
                        question:str, explanation:str, rightAnswer:str):
    url = f'{config.base_url}add_question_OpenAnswer'
    payload = {
        'id_course': id_course,
        'id_test': id_test,
        'id_lesson': id_lesson,
        'id_question': id_question,
        'lesson_name': lesson_name,
        'lesson_description': lesson_descr,
        'question': question,
        'explanation': explanation,
        'rightAnswer': rightAnswer
    }

    try:
        response = requests.post(url, json=payload)
    
        # Controllo del risultato
        if response.status_code == 200:
            print(f'Domanda {id_question} {id_lesson} creata con successo!')
            print('Risposta:', response.json())  # Se restituisci un JSON dal backend
        else:
            print('Errore:', response.status_code, response.text)
    except Exception as e:
        print('Errore nella richiesta:', str(e))

def unlock_lesson(id_course:str, id_student:str, id_lesson:str)->bool:
    '''
        Unlock a lesson for a student
        Args:
            id_course(str)  chiave della tabella mdl_course
            id_student(str) chiave della tabella mdl_user
            id_lesson(str)  chiave della tabella mdl_course_modules
    '''  
    url = f'{config.base_url}unlock_lesson'
    payload = {
        'id_lesson': id_lesson,
        'id_student': id_student,
        'id_course': id_course
    }

    try:
        response = requests.post(url, json=payload)
    
        # Controllo del risultato
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print('Errore:', response.status_code, response.text)
            return False
    except Exception as e:
        print('Errore nella richiesta:', str(e))
        return False

@dataclass
class AnswerData:
    adate:datetime    # when the question was asked
    id_question:str
    result:int 
    timeElapsed:int
    notesTime:int 

    def to_dict(self):
         return {
            "adate": self.adate.isoformat() ,
            "id_question": self.id_question ,
            "result": self.result ,
            "timeElapsed": self.timeElapsed ,
            "notesTime": self.notesTime 
        }

@dataclass
class QuestionData:
    id_question:str
    id_test:str
    id_type: int
    explanation: str
    question:str
    rightAnswer:str
    

    @classmethod
    def from_dict(cls, data: dict[str,Any]) -> "QuestionData":
        # Converte esplicitamente i dati
        return cls(
            id_question=data['id_question'],
            id_test=data['id_test'],
            id_type=data['id_type'],
            explanation=data['explanation'],
            question=data['question'],
            rightAnswer=data['rightAnswer'],
        )


def ask_for_quiz(id_course:str, id_student:str):
    '''
    Ask the Brain Master to suggest a quiz for a student in a course.
    Args:
        id_course(str): unique identifier for the course, e.g. 'openings', 'C42_white', etc.
        id_student(str): unique identifier for the student, e.g. 'gaetano.lazzo'
    Returns:
        A dictionary with the suggested quiz, containing:
               {"action":action.value, 
                "description":Submitter.get_action_description(action),
                "questions": Submitter.get_test(id_course, id_student, action)
                }
    
    '''
    url = f'{config.base_url}suggest_test'
    # I dati che vuoi inviare al servizio
    payload = {
        'id_course': id_course,
        'id_student': id_student
    }

    try:
        response = requests.post(url, json=payload)
    
        # Controllo del risultato
        if response.status_code == 200:
            res = response.json()
            print(f'Quiz ricevuto: {res["action"]} {res["description"]}')
            return res
        else:
            print('Errore:', response.status_code, response.text)
    except Exception as e:
        print('Errore nella richiesta:', str(e))
 

def give_answers(id_course:str, action:int, answers:List[AnswerData]):
    '''
    Send answer to the Brain Master to train it
    Args:
        id_course(str): unique identifier for the course, e.g. 'openings', 'C42_white', etc.
        id_student(str): unique identifier for the student, e.g. 'gaetano.lazzo'
        action(int): action taken by the student
        answers(List[AnswerData]): list of answers given by the student
    '''
    url = f'{config.base_url}give_answers'
       
    # I dati che vuoi inviare al servizio
    payload = {
        'id_course': id_course,
        'id_student': config.id_student,
        'action': action,
        'answers': [a.to_dict() for a in  answers]
    }

    try:
        response = requests.post(url, json=payload)
    
        # Controllo del risultato
        if response.status_code == 200:
            print('Dati inviati con successo.')
            return response.json()
        else:
            print('Errore:', response.status_code, response.text)
    except Exception as e:
        print('Errore nella richiesta:', str(e))

def add_all_lessons(learnBase:str):
    '''
        Add all lessons for a given learning base to the Brain Master.
        Args:
            learnBase(str): unique identifier for the learning base, e.g. 'openings', 'C42_white', etc.
    '''
    quizNames = json_helper.read_struct(os.path.join(DATA_FOLDER,f"lessons_{learnBase}.json"))
    lessons = set()
    for idtest, idlesson in quizNames.items():
        if idlesson in lessons:
            continue
        lessons.add(idlesson)
        id_brainMasterLesson = f'{learnBase}{idlesson}'
        create_lesson(id_brainMasterLesson, learnBase, idlesson, idlesson)
            
def add_all_questions(learnBase:str):
    '''
        Add all questions for a given learning base to the Brain Master.
        Args:
            learnBase(str): unique identifier for the learning base, e.g. 'openings', 'C42_white', etc.
    '''

    quizNames = json_helper.read_struct(os.path.join(DATA_FOLDER,f"lessons_{learnBase}.json"))
    base = LearningBase.learningBases[learnBase]
    for pos in base.positions:
        position = base.positions[pos]
        id_test = f'{learnBase}-{position.idquiz}'
        idlesson = quizNames[str(position.idquiz)]
        id_brainMasterLesson = f'{learnBase}{idlesson}'
        add_question(learnBase, id_test, id_brainMasterLesson, str(position.zobrist),
                        idlesson, idlesson,
                        position.moves, 'no', position.ok)


def unlock_new_lesson(id_course:str)->str:
    '''
    Unlock a new lesson for a student in a course.
    Args:
        id_course(str): unique identifier for the course, e.g. 'openings', 'C42_white', etc.
    '''
    url = f'{config.base_url}suggest_new_lesson'
    payload = {
        'id_course': id_course,
        'id_student': config.id_student
    }

    try:
        response = requests.post(url, json=payload)
    
        # Controllo del risultato
        if response.status_code == 200:                        
            res = response.json()["result"]
            if not res: return False
            print('New lesson to unlock')             
        else:
            print('Errore:', response.status_code, response.text)
            return None
    except Exception as e:
        print('Errore nella richiesta:', str(e))
        return None

    lesson_unlocks:Dict[str,datetime] = {}
    fname =os.path.join(DATA_FOLDER,f'unlock_{id_course}.json')

    if os.path.exists(fname):
        lesson_unlocks = json_helper.read_struct(fname)

    quizNames = json_helper.read_struct(os.path.join(DATA_FOLDER,f"lessons_{id_course}.json"))

    for idtest, idlesson in quizNames.items():
        if idlesson in lesson_unlocks: 
            continue
        id_brainMasterLesson:str = f'{id_course}{idlesson}'
        print(f"Course: {id_course} Unlocking lesson {id_brainMasterLesson}")
        if unlock_lesson(id_course, config.id_student, id_brainMasterLesson):
            print(f"Course: {id_course} lesson {id_brainMasterLesson} unlocked")
            lesson_unlocks[idlesson]= datetime.now()
            json_helper.write_struct(fname, lesson_unlocks)
            return idlesson
        else: 
            print(f"Course: {id_course} lesson {idlesson} was not unlocked")
            return None

    print(f"No lesson to unlock in course {id_course}")
    return None

def add_to_BrainMaster(id_course:str):
    '''
    Add a course to the Brain Master
    '''
    create_course(id_course)
    add_all_lessons(id_course)
    add_all_questions(id_course)
    print(f"Course: {id_course} registered")



if __name__ == "__main__":
    '''
        Main function to add all courses, lessons, and questions to the Brain Master.
    '''
    for id_course in LearningBase.learningBases:
        create_course(id_course)        
        add_all_lessons(id_course)
        add_all_questions(id_course)

   