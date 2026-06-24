from django.contrib.auth.models import User
from django.shortcuts import render, redirect, reverse
from django.contrib.auth import authenticate, login, logout
from django.views import View


# Create your views here.


class LoginView(View):
    template_name = 'login.html' # not exist yet
    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get("password")

        user = authenticate(
            request=request,
            username = username,
            password = password
        )
        if user is not None:
            login(request, user)
            return redirect('/')
        return render(request, self.template_name,{"error": "Invalid username or password."})



class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect(reverse('user_app:login'))


class RegisterView(View):
    template_name = 'register.html' # not exist yet
    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get("password")

        user = User.objects.create_user(username=username, password=password)
        return redirect(reverse('user_app:login'))


