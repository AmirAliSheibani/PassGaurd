from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from user_app.forms import LoginForm
from user_app.models import BackupCode
# Create your views here.


class LoginView(View):

    template_name = 'user_app/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("/")

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
        return redirect("/")

    def post(self, request):
        logout(request)

        return redirect("/")

