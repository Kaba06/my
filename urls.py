from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('clients/', views.client_list, name='client_list'),
    path('clients/add/', views.add_client, name='add_client'),
    path('loan-application/create/', views.loan_application_create, name='loan_application_create'),
    path('loan-applications/', views.loan_application_list, name='loan_application_list'),
    path('approve/<int:app_id>/', views.approve_loan, name='approve_loan'),
    path('disburse/<int:app_id>/', views.disburse_loan, name='disburse_loan'),
    path('record-payment/', views.record_payment, name='record_payment'),
    path('get_installments/<int:client_id>/', views.get_installments, name='get_installments'),
]