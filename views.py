from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.contrib import messages
from .models import *
from datetime import date, timedelta
from django.http import JsonResponse
from decimal import Decimal

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or (hasattr(user, 'userprofile') and user.userprofile.role == 'admin'))

def is_loan_officer(user):
    return user.is_authenticated and (user.is_superuser or (hasattr(user, 'userprofile') and user.userprofile.role in ['admin', 'loan_officer']))

def is_teller(user):
    return user.is_authenticated and (user.is_superuser or (hasattr(user, 'userprofile') and user.userprofile.role in ['admin', 'teller']))

@login_required
def dashboard(request):
    clients_count = Client.objects.count()
    active_loans = Loan.objects.filter(is_active=True).count()
    pending_apps = LoanApplication.objects.filter(status='pending').count()
    total_disbursed = Loan.objects.aggregate(total=models.Sum('principal'))['total'] or 0
    context = {
        'clients_count': clients_count,
        'active_loans': active_loans,
        'pending_apps': pending_apps,
        'total_disbursed': total_disbursed,
    }
    return render(request, 'core/dashboard.html', context)

def custom_logout(request):
    logout(request)
    return redirect('login')

@login_required
@user_passes_test(is_loan_officer)
def client_list(request):
    clients = Client.objects.all()
    return render(request, 'core/client_list.html', {'clients': clients})

@login_required
@user_passes_test(is_loan_officer)
def add_client(request):
    if request.method == 'POST':
        client = Client.objects.create(
            first_name=request.POST['first_name'],
            last_name=request.POST['last_name'],
            national_id=request.POST['national_id'],
            phone=request.POST['phone'],
            address=request.POST.get('address', ''),
            email=request.POST.get('email', '')
        )
        messages.success(request, 'Client added successfully')
        return redirect('client_list')
    return render(request, 'core/add_client.html')

@login_required
@user_passes_test(is_loan_officer)
def loan_application_create(request):
    if request.method == 'POST':
        client_id = request.POST['client']
        product_id = request.POST['product']
        amount = request.POST['amount']
        duration = request.POST['duration']
        purpose = request.POST.get('purpose', '')
        app = LoanApplication.objects.create(
            client_id=client_id,
            product_id=product_id,
            amount_requested=amount,
            duration_months=duration,
            purpose=purpose,
            status='pending'
        )
        messages.success(request, 'Loan application submitted')
        return redirect('loan_application_list')
    clients = Client.objects.all()
    products = LoanProduct.objects.filter(is_active=True)
    return render(request, 'core/loan_application_form.html', {'clients': clients, 'products': products})

@login_required
@user_passes_test(is_loan_officer)
def loan_application_list(request):
    apps = LoanApplication.objects.all().order_by('-applied_date')
    return render(request, 'core/loan_application_list.html', {'applications': apps})

@login_required
@user_passes_test(is_admin)
def approve_loan(request, app_id):
    app = get_object_or_404(LoanApplication, id=app_id)
    if app.status == 'pending':
        app.status = 'approved'
        app.approved_by = request.user
        app.approval_date = date.today()
        app.save()
        messages.success(request, f'Application #{app.id} approved')
    return redirect('loan_application_list')

@login_required
@user_passes_test(is_admin)
def disburse_loan(request, app_id):
    app = get_object_or_404(LoanApplication, id=app_id, status='approved')
    if request.method == 'POST':
        total_interest = app.calculate_total_interest()
        total_repayable = app.amount_requested + total_interest
        monthly = app.calculate_monthly_payment()
        loan = Loan.objects.create(
            application=app,
            client=app.client,
            product=app.product,
            principal=app.amount_requested,
            total_interest=total_interest,
            total_repayable=total_repayable,
            monthly_payment=monthly,
            disbursement_date=date.today(),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30*app.duration_months),
            is_active=True
        )
        for i in range(1, app.duration_months + 1):
            due = date.today() + timedelta(days=30*i)
            RepaymentSchedule.objects.create(
                loan=loan,
                installment_number=i,
                due_date=due,
                amount_due=monthly,
                amount_paid=0,
                is_paid=False
            )
        app.status = 'disbursed'
        app.save()
        messages.success(request, f'Loan #{loan.id} disbursed')
        return redirect('loan_application_list')
    return render(request, 'core/disburse_confirm.html', {'application': app})

@login_required
@user_passes_test(is_teller)
def record_payment(request):
    if request.method == 'POST':
        client_id = request.POST['client']
        amount = request.POST['amount']
        installment_id = request.POST['installment']
        installment = get_object_or_404(RepaymentSchedule, id=installment_id)
        payment = Payment.objects.create(
            client_id=client_id,
            payment_type='loan_installment',
            amount=amount,
            date=date.today(),
            received_by=request.user,
            installment=installment
        )
        installment.amount_paid += Decimal(amount)
        if installment.amount_paid >= installment.amount_due:
            installment.is_paid = True
            installment.paid_date = date.today()
        late_fee = installment.calculate_late_fee()
        if late_fee > 0:
            installment.late_fee_charged = late_fee
        installment.save()
        messages.success(request, 'Payment recorded')
        return redirect('record_payment')
    clients = Client.objects.all()
    return render(request, 'core/record_payment.html', {'clients': clients})

@login_required
@user_passes_test(is_teller)
def get_installments(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    installments = RepaymentSchedule.objects.filter(
        loan__client=client,
        is_paid=False,
        loan__is_active=True
    ).select_related('loan')
    data = [{'id': inst.id, 'label': f"Loan #{inst.loan.id} - Installment {inst.installment_number} - Due {inst.due_date} - Amount {inst.amount_due}"} for inst in installments]
    return JsonResponse(data, safe=False)