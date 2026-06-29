from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date, timedelta

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('loan_officer', 'Loan Officer'),
        ('teller', 'Teller'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='loan_officer')
    phone = models.CharField(max_length=15, blank=True)
    def __str__(self):
        return f"{self.user.username} - {self.role}"

class Client(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    national_id = models.CharField(max_length=20, unique=True)
    phone = models.CharField(max_length=15)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    date_registered = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    id_document_image = models.FileField(upload_to='ids/', blank=True, null=True)
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.national_id})"
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class LoanProduct(models.Model):
    INTEREST_TYPE = (('flat', 'Flat Rate'), ('declining', 'Declining Balance'))
    name = models.CharField(max_length=100)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    interest_type = models.CharField(max_length=20, choices=INTEREST_TYPE, default='flat')
    min_amount = models.DecimalField(max_digits=12, decimal_places=2)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2)
    default_duration_months = models.IntegerField(default=6)
    late_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5.0)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.name} ({self.interest_rate}% {self.interest_type})"

class LoanApplication(models.Model):
    STATUS_CHOICES = (('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('disbursed', 'Disbursed'))
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    product = models.ForeignKey(LoanProduct, on_delete=models.CASCADE)
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2)
    duration_months = models.IntegerField()
    purpose = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_date = models.DateField(auto_now_add=True)
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_loans')
    approval_date = models.DateField(null=True, blank=True)
    def __str__(self):
        return f"Application {self.id} - {self.client} - {self.status}"
    def calculate_total_interest(self):
        P = float(self.amount_requested)
        r = float(self.product.interest_rate) / 100
        n = self.duration_months
        if self.product.interest_type == 'flat':
            interest = P * r * n
        else:
            interest = (P * r * (n + 1)) / 2
        return Decimal(interest).quantize(Decimal('0.01'))
    def calculate_monthly_payment(self):
        total = self.amount_requested + self.calculate_total_interest()
        return (total / self.duration_months).quantize(Decimal('0.01'))

class Loan(models.Model):
    application = models.OneToOneField(LoanApplication, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    product = models.ForeignKey(LoanProduct, on_delete=models.CASCADE)
    principal = models.DecimalField(max_digits=12, decimal_places=2)
    total_interest = models.DecimalField(max_digits=12, decimal_places=2)
    total_repayable = models.DecimalField(max_digits=12, decimal_places=2)
    monthly_payment = models.DecimalField(max_digits=12, decimal_places=2)
    disbursement_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"Loan #{self.id} - {self.client}"

class RepaymentSchedule(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='schedule')
    installment_number = models.IntegerField()
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_date = models.DateField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    late_fee_charged = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    def __str__(self):
        return f"Installment {self.installment_number} - Loan {self.loan.id}"
    def calculate_late_fee(self):
        if self.is_paid or self.due_date >= date.today():
            return Decimal(0)
        days_late = (date.today() - self.due_date).days
        if days_late <= 0:
            return Decimal(0)
        product = self.loan.product
        overdue_amount = self.amount_due - self.amount_paid
        if overdue_amount <= 0:
            return Decimal(0)
        months_late = days_late / 30
        fee_percent = product.late_fee_percent / 100
        fee = overdue_amount * fee_percent * months_late
        return fee.quantize(Decimal('0.01'))

class Payment(models.Model):
    PAYMENT_TYPE = (('loan_installment', 'Loan Installment'), ('savings_deposit', 'Savings Deposit'), ('savings_withdrawal', 'Savings Withdrawal'))
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    payment_type = models.CharField(max_length=30, choices=PAYMENT_TYPE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=date.today)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    reference = models.CharField(max_length=100, blank=True)
    installment = models.ForeignKey(RepaymentSchedule, null=True, blank=True, on_delete=models.SET_NULL)
    journal_entry_made = models.BooleanField(default=False)
    def __str__(self):
        return f"{self.payment_type} - {self.amount} on {self.date}"

class SavingsAccount(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    account_number = models.CharField(max_length=20, unique=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    opened_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"Savings {self.account_number} - {self.client}"

class JournalEntry(models.Model):
    date = models.DateField(default=date.today)
    description = models.CharField(max_length=200)
    debit_account = models.CharField(max_length=50)
    credit_account = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    related_payment = models.ForeignKey(Payment, null=True, blank=True, on_delete=models.SET_NULL)
    def __str__(self):
        return f"Journal {self.id}: {self.description}"

# Signal to auto-create journal entries when a payment is saved
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Payment)
def create_journal_entry(sender, instance, created, **kwargs):
    if created and not instance.journal_entry_made:
        if instance.payment_type == 'loan_installment':
            JournalEntry.objects.create(
                date=instance.date,
                description=f"Loan payment from {instance.client}",
                debit_account="Cash/Bank",
                credit_account="Loan Receivable",
                amount=instance.amount,
                related_payment=instance
            )
        elif instance.payment_type == 'savings_deposit':
            JournalEntry.objects.create(
                date=instance.date,
                description=f"Savings deposit from {instance.client}",
                debit_account="Cash/Bank",
                credit_account="Savings Liability",
                amount=instance.amount,
                related_payment=instance
            )
        instance.journal_entry_made = True
        instance.save()