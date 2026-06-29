from django.contrib import admin
from .models import *

admin.site.register(UserProfile)
admin.site.register(Client)
admin.site.register(LoanProduct)
admin.site.register(LoanApplication)
admin.site.register(Loan)
admin.site.register(RepaymentSchedule)
admin.site.register(Payment)
admin.site.register(SavingsAccount)
admin.site.register(JournalEntry)