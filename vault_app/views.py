from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from user_app.forms import LoginForm, RegisterForm
from user_app.models import BackupCode
from user_app.services.user_services import UserService


# Create your views here.


class LoginView(View):

    template_name = 'user_app/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("core:home")

        form = LoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        user = authenticate(
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password']
        )

        if user is None:
            form.add_error(None, "Invalid username or password")

            return render(request, self.template_name, {'form': form})

        login(request, user)
        return render(request, self.template_name, {'form': form})


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect("core:home")

    def post(self, request):
        logout(request)

        return redirect("core:home")


class RegisterView(View):
    template_name = 'user_app/register.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("core:home")

        form = RegisterForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        user = UserService.register(
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password']
        )
        login(request, user)
        return redirect("core:home")



