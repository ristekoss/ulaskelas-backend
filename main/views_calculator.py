import logging

from rest_framework.decorators import api_view
from rest_framework import status
from .serializers import CalculatorSerializer, ScoreComponentSerializer

from .utils import response, validate_body, validate_params
from .models import Calculator, Profile, Course, ScoreComponent
from django.db.models import F

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST', 'DELETE'])
def calculator(request):

    user = Profile.objects.get(username=str(request.user))
    if request.method == 'GET':
        calculators = Calculator.objects.filter(user = user)
        return response(data=CalculatorSerializer(calculators, many=True).data)

    if request.method == 'POST':
        is_valid = validate_body(request, ['course_code'])

        if is_valid != None:
            return is_valid

        course_code = request.data.get('course_code')
        course = Course.objects.filter(code=course_code).first()

        if course is None:
            return response(error="Course not found", status=status.HTTP_404_NOT_FOUND)

        calculator = Calculator.objects.filter(user=user, course=course).first()

        if calculator is None:
            calculator = Calculator.objects.create(user=user, course=course)
            return response(data=CalculatorSerializer(calculator).data, status=status.HTTP_201_CREATED)

        return response(error="Course calculator already exists", status=status.HTTP_409_CONFLICT)
    
    if request.method == 'DELETE':
        is_valid = validate_params(request, ['id'])

        if is_valid != None:
            return is_valid

        calculator_id = request.query_params.get('id')
        calculator = Calculator.objects.filter(id=calculator_id).first()

        if calculator is None:
            return response(error="Calculator not found", status=status.HTTP_404_NOT_FOUND)

        calculator.delete()
        return response(status=status.HTTP_200_OK)

@api_view(['GET', 'POST', 'PUT', 'DELETE'])
def score_component(request):

    if request.method == 'GET':

        is_valid = validate_params(request, ['calculator_id'])

        if is_valid != None:
            is_valid

        calculator_id = request.query_params.get('calculator_id')
        calculator = Calculator.objects.filter(id=calculator_id).first()

        if calculator is None:
            return response(error="Calculator not found", status=status.HTTP_404_NOT_FOUND)

        score_components = ScoreComponent.objects.filter(calculator=calculator)
        return response(data=ScoreComponentSerializer(score_components, many=True).data)
    
    if request.method == 'POST':

        is_valid = validate_body(request, ['calculator_id', 'name', 'weight', 'score'])

        if is_valid != None:
            is_valid

        calculator_id = request.data.get('calculator_id')
        name = request.data.get('name')
        weight = request.data.get('weight')
        score = request.data.get('score')

        calculator = Calculator.objects.filter(id=calculator_id).first()

        if calculator is None:
            return response(error="Calculator not found", status=status.HTTP_404_NOT_FOUND)

        score_component = ScoreComponent.objects.create(calculator=calculator, name=name, weight=weight, score=score)

        calculator.total_score += (score * weight / 100)
        calculator.total_percentage += weight

        calculator.save()
        
        return response(data=ScoreComponentSerializer(score_component).data, status=status.HTTP_201_CREATED)

    if request.method == 'PUT':
        is_valid = validate_body(request, ['id', 'name', 'weight', 'score'])

        if is_valid != None:
            is_valid

        component_id = request.data.get('id')
        name = request.data.get('name')
        weight = request.data.get('weight')
        score = request.data.get('score')

        score_component = ScoreComponent.objects.filter(id=component_id).first()

        if score_component is None:
            return response(error="Score component not found", status=status.HTTP_404_NOT_FOUND)

        calculator = Calculator.objects.filter(id=score_component.calculator.id).first()

        calculator.total_score -= (score_component.score * score_component.weight / 100)
        calculator.total_percentage -= score_component.weight

        score_component.name = name
        score_component.weight = weight
        score_component.score = score

        score_component.save()

        calculator.total_score += (score_component.score * score_component.weight / 100)
        calculator.total_percentage += score_component.weight

        calculator.save()
        return response(data=ScoreComponentSerializer(score_component).data, status=status.HTTP_201_CREATED)

    if request.method == 'DELETE':
        is_valid = validate_params(request, ['id'])

        if is_valid != None:
            return is_valid

        component_id = request.query_params.get('id')

        score_component = ScoreComponent.objects.filter(id=component_id).first()

        if score_component is None:
            return response(error="Score component not found", status=status.HTTP_404_NOT_FOUND)

        calculator = Calculator.objects.filter(id=score_component.calculator.id).first()

        calculator.total_score -= (score_component.score * score_component.weight / 100)
        calculator.total_percentage -= score_component.weight

        score_component.delete()
        calculator.save()

        return response(status=status.HTTP_200_OK)

    