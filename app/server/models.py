import string
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.contrib.staticfiles.storage import staticfiles_storage


class Project(models.Model):
    DOCUMENT_CLASSIFICATION = 'DocumentClassification'
    SEQUENCE_LABELING = 'SequenceLabeling'
    Seq2seq = 'Seq2seq'

    PROJECT_CHOICES = (
        (DOCUMENT_CLASSIFICATION, 'document classification'),
        (SEQUENCE_LABELING, 'sequence labeling'),
        (Seq2seq, 'sequence to sequence'),
    )

    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500)
    guideline = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    users = models.ManyToManyField(User)
    project_type = models.CharField(max_length=30, choices=PROJECT_CHOICES)

    def is_type_of(self, project_type):
        return project_type == self.project_type

    @property
    def image(self):
        if self.is_type_of(self.DOCUMENT_CLASSIFICATION):
            url = staticfiles_storage.url('images/cat-1045782_640.jpg')
        elif self.is_type_of(self.SEQUENCE_LABELING):
            url = staticfiles_storage.url('images/cat-3449999_640.jpg')
        elif self.is_type_of(self.Seq2seq):
            url = staticfiles_storage.url('images/tiger-768574_640.jpg')

        return url

    def get_template(self):
        if self.is_type_of(Project.DOCUMENT_CLASSIFICATION):
            template_name = 'annotation/document_classification.html'
        elif self.is_type_of(Project.SEQUENCE_LABELING):
            template_name = 'annotation/sequence_labeling.html'
        elif self.is_type_of(Project.Seq2seq):
            template_name = 'annotation/seq2seq.html'
        else:
            raise ValueError('Template does not exist')

        return template_name

    def get_documents(self, is_null=True):
        docs = self.documents.all()
        if self.is_type_of(Project.DOCUMENT_CLASSIFICATION):
            docs = docs.filter(doc_annotations__isnull=is_null)
        elif self.is_type_of(Project.SEQUENCE_LABELING):
            docs = docs.filter(seq_annotations__isnull=is_null)
        elif self.is_type_of(Project.Seq2seq):
            docs = docs.filter(seq2seq_annotations__isnull=is_null)
        else:
            raise ValueError('Invalid project_type')

        return docs

    def get_project_serializer(self):
        from .serializers import DocumentSerializer
        from .serializers import SequenceSerializer
        from .serializers import Seq2seqSerializer
        if self.is_type_of(Project.DOCUMENT_CLASSIFICATION):
            return DocumentSerializer
        elif self.is_type_of(Project.SEQUENCE_LABELING):
            return SequenceSerializer
        elif self.is_type_of(Project.Seq2seq):
            return Seq2seqSerializer
        else:
            raise ValueError('Invalid project_type')

    def get_annotation_serializer(self):
        from .serializers import DocumentAnnotationSerializer
        from .serializers import SequenceAnnotationSerializer
        from .serializers import Seq2seqAnnotationSerializer
        if self.is_type_of(Project.DOCUMENT_CLASSIFICATION):
            return DocumentAnnotationSerializer
        elif self.is_type_of(Project.SEQUENCE_LABELING):
            return SequenceAnnotationSerializer
        elif self.is_type_of(Project.Seq2seq):
            return Seq2seqAnnotationSerializer

    def get_annotation_class(self):
        if self.is_type_of(Project.DOCUMENT_CLASSIFICATION):
            return DocumentAnnotation
        elif self.is_type_of(Project.SEQUENCE_LABELING):
            return SequenceAnnotation
        elif self.is_type_of(Project.Seq2seq):
            return Seq2seqAnnotation

    def __str__(self):
        return self.name


class Label(models.Model):
    KEY_CHOICES = ((u, c) for u, c in zip(string.ascii_lowercase, string.ascii_lowercase))
    COLOR_CHOICES = ()

    text = models.CharField(max_length=100)
    shortcut = models.CharField(max_length=10, choices=KEY_CHOICES)
    project = models.ForeignKey(Project, related_name='labels', on_delete=models.CASCADE)
    background_color = models.CharField(max_length=7, default='#209cee')
    text_color = models.CharField(max_length=7, default='#ffffff')

    def __str__(self):
        return self.text

    class Meta:
        unique_together = (
            ('project', 'text'),
            ('project', 'shortcut')
        )


class Document(models.Model):
    text = models.TextField()
    project = models.ForeignKey(Project, related_name='documents', on_delete=models.CASCADE)

    def get_annotations(self):
        if self.project.is_type_of(Project.DOCUMENT_CLASSIFICATION):
            return self.doc_annotations.all()
        elif self.project.is_type_of(Project.SEQUENCE_LABELING):
            return self.seq_annotations.all()
        elif self.project.is_type_of(Project.Seq2seq):
            return self.seq2seq_annotations.all()

    def make_dataset(self):
        if self.project.is_type_of(Project.DOCUMENT_CLASSIFICATION):
            return self.make_dataset_for_classification()
        elif self.project.is_type_of(Project.SEQUENCE_LABELING):
            return self.seq_annotations.all()
        elif self.project.is_type_of(Project.Seq2seq):
            return self.make_dataset_for_seq2seq()

    def make_dataset_for_classification(self):
        annotations = self.get_annotations()
        dataset = [[a.document.id, a.document.text, a.label.text, a.user.username]
                   for a in annotations]
        return dataset

    def make_dataset_for_seq2seq(self):
        annotations = self.get_annotations()
        dataset = [[a.document.id, a.document.text, a.text, a.user.username]
                   for a in annotations]
        return dataset

    def __str__(self):
        return self.text[:50]


class Annotation(models.Model):
    prob = models.FloatField(default=0.0)
    manual = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class DocumentAnnotation(Annotation):
    document = models.ForeignKey(Document, related_name='doc_annotations', on_delete=models.CASCADE)
    label = models.ForeignKey(Label, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('document', 'user', 'label')


class SequenceAnnotation(Annotation):
    document = models.ForeignKey(Document, related_name='seq_annotations', on_delete=models.CASCADE)
    label = models.ForeignKey(Label, on_delete=models.CASCADE)
    start_offset = models.IntegerField()
    end_offset = models.IntegerField()

    def clean(self):
        if self.start_offset >= self.end_offset:
            raise ValidationError('start_offset is after end_offset')

    class Meta:
        unique_together = ('document', 'user', 'label', 'start_offset', 'end_offset')


class Seq2seqAnnotation(Annotation):
    document = models.ForeignKey(Document, related_name='seq2seq_annotations', on_delete=models.CASCADE)
    text = models.TextField()

    class Meta:
        unique_together = ('document', 'user', 'text')
