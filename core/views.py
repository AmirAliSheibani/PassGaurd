from django.shortcuts import render

# Create your views here.

def home_view(request): #test
    return render(request, "core/test.html")