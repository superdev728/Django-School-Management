from model_utils.models import TimeStampedModel

from django.db import models, OperationalError
from django.conf import settings
from django.urls import reverse

from teachers.models import Teacher


class Department(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    short_name = models.CharField(
        'Department Short Form',
        max_length=5
    )
    code = models.PositiveIntegerField()
    short_description = models.TextField(
        help_text='Write short description about the department.',
        blank=True,
        null=True
    )
    department_icon = models.ImageField(
        help_text='Upload an image/icon for the department',
        upload_to='department_icon/',
        blank=True,
        null=True
    )
    head = models.ForeignKey(
        Teacher, on_delete=models.CASCADE,
        blank=True, null=True
    )
    current_batch = models.ForeignKey(
        'Batch', on_delete=models.CASCADE,
        blank=True, null=True,
        related_name='current_batches'
    )
    batches = models.ManyToManyField(
        'Batch',
        related_name='department_batches',
        blank=True
    )
    establish_date = models.DateField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING,
        null=True
    )

    def dept_code(self):
        if not self.code:
            return ""
        return self.code

    def __str__(self):
        return str(self.name)
    
    def create_resource(self):
        return reverse('academics:create_department')


class AcademicSession(TimeStampedModel):
    year = models.PositiveIntegerField(unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING, null=True)

    def __str__(self):
        return '{} - {}'.format(self.year, self.year + 1)
    
    def create_resource(self):
        return reverse('academics:create_academic_session')


class Semester(TimeStampedModel):
    number = models.PositiveIntegerField(unique=True)
    guide = models.ForeignKey(
        Teacher, on_delete=models.CASCADE,
        default=None, null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING, null=True
    )

    class Meta:
        ordering = ['number', ]

    def __str__(self):
        if self.number == 1:
            return '1st'
        if self.number == 2:
            return '2nd'
        if self.number == 3:
            return '3rd'
        if self.number and 3 < self.number <= 12:
            return '%sth' % self.number
    
    def create_resource(self):
        return reverse('academics:create_semester')


class Subject(TimeStampedModel):
    name = models.CharField(max_length=50)
    subject_code = models.PositiveIntegerField(unique=True)
    book_cover = models.ImageField(
        upload_to='subjects/',
        default='subjects/bookcover.png'
    )
    instructor = models.ForeignKey(
        Teacher, on_delete=models.CASCADE,
        blank=True, null=True
    )
    theory_marks = models.PositiveIntegerField(blank=True, null=True)
    practical_marks = models.PositiveIntegerField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING, null=True)

    def __str__(self):
        return "{} ({})".format(self.name, self.subject_code)
    
    def create_resource(self):
        return reverse('academics:create_subject')


class Batch(TimeStampedModel):
    year = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    number = models.PositiveIntegerField('Batch Number')
    department = models.ForeignKey(Department, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = 'Batches'
        unique_together = ['year', 'department', 'number']

    def __str__(self):
        return f'{self.department.name} Batch {self.number} ({self.year})'


class TempSerialID(TimeStampedModel):
    student = models.OneToOneField('students.Student', on_delete=models.CASCADE,
                                   related_name='student_serial')
    department = models.ForeignKey(Department, on_delete=models.CASCADE,
                                   related_name='temp_serials')
    year = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    serial = models.CharField(max_length=50, blank=True)

    # class Meta:
    #     unique_together = ['department', 'year']

    def __str__(self):
        return self.serial

    def save(self, *args, **kwargs):
        if self.student.admission_student.admitted:
            super().save(*args, **kwargs)
        else:
            raise OperationalError('Please check if student is admitted or not.')

    def get_serial(self):
        # Get current year last two digit
        yf = str(self.student.ac_session)[-2:]
        # Get current batch of student's department
        bn = self.student.batch.number
        # Get department code
        dc = self.department.code
        # Get admission serial of student by department
        syl = self.serial

        # return something like: 21-15-666-15
        return f'{yf}-{bn}-{dc}-{syl}'
