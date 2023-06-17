from datetime import date, timedelta, datetime
from collections import OrderedDict

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, UpdateView
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from academics.models import (
    Department, Semester, Subject, Batch, AcademicSession
)
from result.models import SubjectGroup
from students.models import Student, AdmissionStudent, CounselingComment
from students.forms import (
    StudentForm, AdmissionForm, StudentRegistrantUpdateForm,
    CounselingDataForm, StudentUpdateForm
)
from students.filters import AlumniFilter
from students.tasks import send_admission_confirmation_email
from permission_handlers.administrative import (
    user_is_admin_or_su,
    user_is_admin_su_or_ac_officer,
    user_is_student_or_administrative,
)
from permission_handlers.basic import user_is_verified


@user_passes_test(user_is_admin_su_or_ac_officer)
def students_dashboard_index(request):
    """
    Dashboard for online admission system. 
    """
    unpaid_registrants = AdmissionStudent.objects.filter(paid=False)
    all_applicants = AdmissionStudent.objects.all().order_by('-created')
    admitted_students = AdmissionStudent.objects.filter(admitted=True, paid=True)
    paid_registrants = AdmissionStudent.objects.filter(paid=True, admitted=False)
    rejected_applicants = AdmissionStudent.objects.filter(rejected=True)
    offline_applicants = AdmissionStudent.objects.filter(application_type='2')

    # List of months since first application registration date
    try:
        first_application_date = AdmissionStudent.objects.order_by(
            'created')[0].created.date()
        last_application_date = date.today()
        dates = [str(first_application_date), str(last_application_date)]
        months_start, months_end = [
            datetime.strptime(_, '%Y-%m-%d') for _ in dates
        ]
        # List of month to display options in student dashboard index
        month_list = OrderedDict(
            ((months_start + timedelta(_)).strftime(r"%B-%Y"), None) for _ in
            range((months_end - months_start).days)
        ).keys()
    except IndexError:
        month_list = []

    context = {
        'all_applicants': all_applicants,
        'unpaid_registrants': unpaid_registrants,
        'admitted_students': admitted_students,
        'paid_registrants': paid_registrants,
        'rejected_applicants': rejected_applicants,
        'offline_applicants': offline_applicants,
        'month_list': month_list,
    }
    return render(request, 'students/dashboard_index.html', context)


@user_passes_test(user_is_admin_su_or_ac_officer)
def all_applicants(request):
    """Display all registered students list"""
    registrants = AdmissionStudent.objects.all().order_by('-created')
    ctx = {
        'registrants': registrants,
    }
    return render(request, 'students/all_applicants.html', ctx)


@user_passes_test(user_is_admin_su_or_ac_officer)
def admitted_students_list(request):
    """ 
    Returns list of students admitted from online registration.
    """
    admitted_students = AdmissionStudent.objects.filter(admitted=True, paid=True)
    context = {
        'admitted_students': admitted_students,
    }
    return render(request, 'students/dashboard_all_cleared_students.html', context)


@user_passes_test(user_is_admin_su_or_ac_officer)
def paid_registrants(request):
    """ 
    Returns list of students already paid from online registration.
    """
    paid_students = AdmissionStudent.objects.filter(paid=True, admitted=False)
    context = {
        'paid_students': paid_students,
    }
    return render(request, 'students/dashboard_paid_students.html', context)


@user_passes_test(user_is_admin_su_or_ac_officer)
def unpaid_registrants(request):
    """
    Returns list of students haven't paid admission fee yet.
    """
    unpaid_registrants_list = AdmissionStudent.objects.filter(paid=False)
    context = {
        'unpaid_applicants': unpaid_registrants_list,
    }
    return render(request, 'students/unpaid_applicants.html', context)


@user_passes_test(user_is_admin_su_or_ac_officer)
def rejected_registrants(request):
    ctx = {
        'rejected_registrants': AdmissionStudent.objects.filter(rejected=True),
    }
    return render(request, 'students/list/rejected_registrants.html', ctx)


def get_json_batch_data(request, *args, **kwargs):
    selected_department_code = kwargs.get('department_code')
    department_batches = list(
        Batch.objects.filter(department__code=selected_department_code).values()
    )
    return JsonResponse({'data': department_batches})


@user_passes_test(user_is_admin_su_or_ac_officer)
def admission_confirmation(request):
    """
    If request is get, show list of applicants to be admitted finally as student,
    for POST request, it will create Student, RegularStudent.
    """
    selected_registrants = AdmissionStudent.objects.filter(
        admitted=True, 
        paid=True, 
        rejected=False,
        assigned_as_student=False)
    departments = Department.objects.order_by('name')
    batches = Batch.objects.all()
    sessions = AcademicSession.objects.all()
    ctx = {
        'selected_registrants': selected_registrants,
        'departments': departments,
        'sessions': sessions
    }

    if request.method == 'POST':
        dept_code = request.POST.get('department_code')
        batch_id = request.POST.get('batch_id')
        session_id = request.POST.get('session_id')
        # If confirmation processes is followed by checkmarks,
        # then we confirm admission for only selected candidates.
        checked_registrant_ids = request.POST.getlist('registrant_choice')

        try:
            to_be_admitted = selected_registrants.filter(
                choosen_department__code=int(dept_code)
            )
            if checked_registrant_ids:
                to_be_admitted = AdmissionStudent.objects.filter(
                    id__in=list(map(int, checked_registrant_ids))
                )
        except ValueError:
            messages.add_message(
                request,
                messages.ERROR,
                'Please select applicants to permit for admission.'
            )
            to_be_admitted = []

        try:
            # get first semester to admit in first semester.
            semester_number = 1
            semester = Semester.objects.get(number=semester_number)
            batch = Batch.objects.get(id=batch_id)
        except Semester.DoesNotExist:
            messages.add_message(
                request,
                messages.ERROR,
                f'Given semester number {semester_number} not found!'
            )
        except Batch.DoesNotExist:
            messages.add_message(
                request,
                messages.ERROR,
                'Please select/create a batch first.'
            )

        students = []
        for candidate in to_be_admitted:
            try:
                session = AcademicSession.objects.get(id=session_id)
            except ValueError:
                messages.add_message(
                    request,
                    messages.ERROR,
                    'Please choose a valid session.'
                )
            # If student.save() doesn't raise any exceptions, 
            # we save student, except, we skip making student object.
            try:
                student = Student.objects.create(
                    admission_student=candidate,
                    semester=semester,
                    batch=batch,
                    ac_session=session,
                    admitted_by=request.user,
                )
                students.append(student)
            except:
                pass
        ctx['students'] = students
        return render(request, 'students/list/confirm_admission.html', ctx)
    else:
        return render(request, 'students/list/confirm_admission.html', ctx)


@user_passes_test(user_is_admin_su_or_ac_officer)
def admit_student(request, pk):
    """ 
    Admit applicant found by id/pk into chosen department
    """
    applicant = get_object_or_404(AdmissionStudent, pk=pk)
    if request.method == 'POST':
        form = AdmissionForm(request.POST, instance=applicant)
        if form.is_valid():
            student = form.save(commit=False)
            student.admitted = True
            student.paid = True
            student.admission_date = date.today()
            send_admission_confirmation_email.delay(student.id)
            return redirect('students:admitted_student_list')
    else:
        form = AdmissionForm()
        context = {'form': form, 'applicant': applicant}
    return render(request, 'students/dashboard_admit_student.html', context)


@user_passes_test(user_is_admin_su_or_ac_officer)
def mark_as_paid_or_unpaid(request):
    """ Change student applicants payment status """
    if request.method == 'POST':
        registrant_pk = request.POST.get('registrant_id')
        applicant = get_object_or_404(AdmissionStudent, pk=registrant_pk)
        if not applicant.paid:
            # If applicant didn't pay fee already, change to paid
            applicant.paid = True
            applicant.save()
            return JsonResponse({'data': True})
        # If applicant already paid the amount, change to unpaid
        applicant.paid = False
        applicant.save()
        return JsonResponse({'data': False})


@user_passes_test(user_is_admin_su_or_ac_officer)
def update_online_registrant(request, pk):
    """ 
    Update applicants details, counseling information
    """
    applicant = get_object_or_404(AdmissionStudent, pk=pk)
    counseling_records = CounselingComment.objects.filter(registrant_student=applicant)
    if request.method == 'POST':
        form = StudentRegistrantUpdateForm(
            request.POST,
            request.FILES,
            instance=applicant)
        if form.is_valid():
            form.save()
            return redirect('students:paid_registrants')
    else:
        form = StudentRegistrantUpdateForm(instance=applicant)
        counseling_form = CounselingDataForm()
        context = {
            'form': form,
            'applicant': applicant,
            'counseling_records': counseling_records,
            'counseling_form': counseling_form}
    return render(request, 'students/dashboard_update_online_applicant.html', context)


@user_passes_test(user_is_admin_su_or_ac_officer)
def add_counseling_data(request, student_id):
    registrant = get_object_or_404(AdmissionStudent, id=student_id)
    if request.method == 'POST':
        form = CounselingDataForm(request.POST)
        if form.is_valid():
            counseling_comment = form.save(commit=False)
            counseling_comment.counselor = request.user
            counseling_comment.registrant_student = registrant
            counseling_comment.save()
            return redirect('students:update_online_registrant', pk=student_id)


@user_passes_test(user_is_admin_su_or_ac_officer)
def add_student_view(request):
    """
    :param request:
    :return: admission form to
    logged in user.
    """
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            student = form.save(commit=False)
            # check student as offline registration
            student.application_type = '2'
            student.save()
            return redirect('students:all_applicants')
    else:
        form = StudentForm()
    context = {'form': form}
    return render(request, 'students/addstudent.html', context)


@user_passes_test(user_is_admin_su_or_ac_officer)
def students_view(request):
    """
    :param request:
    :return: renders student list with all department
    and semesters list.
    """
    all_students = Student.objects.select_related(
        'admission_student', 'semester', 'ac_session').all()
    context = {
        'students': all_students,
    }
    return render(request, 'students/list/students_list.html', context)


@user_passes_test(user_is_admin_su_or_ac_officer)
def students_by_department_view(request, pk):
    dept_name = Department.objects.get(pk=pk)
    students = Student.objects.select_related(
        'department', 'semester', 'ac_session').filter(department=dept_name)
    context = {'students': students, }
    return render(request, 'students/students_by_department.html', context)


class StudentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    renders a student update form to update students details.
    """
    model = Student
    form_class = StudentUpdateForm
    template_name = 'students/update_student.html'

    def test_func(self):
        user = self.request.user
        return user_is_admin_su_or_ac_officer(user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect('account:profile_complete')
        return redirect('account_login')

    def post(self, request, pk, *args, **kwargs):
        obj = get_object_or_404(Student, pk=pk)
        form = StudentUpdateForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect('students:student_details', pk=obj.pk)

    def get_success_url(self):
        student_id = self.kwargs['pk']
        return reverse_lazy('students:student_details', kwargs={'pk': student_id})


class StudentDetailsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Student
    template_name = 'students/student_details.html'

    def test_func(self):
        user = self.request.user
        return user_is_admin_su_or_ac_officer(user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect('account:profile_complete')
        return redirect('account_login')

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        obj = kwargs['object']
        pk = obj.id
        student = Student.objects.get(pk=pk)
        # get student object
        # for showing subjects in option form
        student_subject_qs = SubjectGroup.objects.filter(
            department=student.admission_student.choosen_department,
            semester=student.semester
        )
        context['subjects'] = student_subject_qs
        # getting result objects
        results = student.results.all()
        context['results'] = results
        return context


@user_passes_test(user_is_admin_su_or_ac_officer)
def student_delete_view(request, pk):
    student = Student.objects.get(pk=pk)
    student.delete()
    return redirect('students:all_student')


class AlumnusListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Student
    context_object_name = 'alumnus'
    template_name = 'students/list/alumnus.html'

    def test_func(self):
        user = self.request.user
        return user_is_verified(user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect('account:profile_complete')
        return redirect('account_login')

    def get_queryset(self):
        queryset = Student.alumnus.all()
        return queryset
    
    def get_context_data(self, *args, object_list=None, **kwargs):
        ctx = super().get_context_data(*args, object_list=object_list, **kwargs)
        alumnus = Student.alumnus.all()
        f = AlumniFilter(self.request.GET, queryset=alumnus)
        ctx['filter'] = f
        return ctx
