from django.urls import path
from recommend import views
from .views import calculate_precision_recall

urlpatterns = [
    path('', views.index, name='index'),
    path('signup/', views.signUp, name='signup'),
    path('login/', views.Login, name='login'),
    path('logout/', views.Logout, name='logout'),
    path('<int:movie_id>/', views.detail, name='detail'),
    path('watch/', views.watch, name='watch'),
    path('recommend/', views.recommend, name='recommend'),
    path('calculate_precision_recall/', calculate_precision_recall, name='calculate_precision_recall'),
    path('content_recommendation/<int:movie_id>/', views.content_based_recommendation, name='content_recommendation'),

]
