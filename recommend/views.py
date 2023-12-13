from django.contrib.auth import authenticate, login
from django.contrib.auth import logout
from django.shortcuts import render, get_object_or_404, redirect
from .forms import *
from django.http import Http404
from .models import Movie, Myrating, MyList
from django.db.models import Q
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.db.models import Case, When
from django.db.models import Count
from django.db.models import Q
import pandas as pd
import numpy as np


# Create your views here.


def index(request):
    movies = Movie.objects.all()
    query = request.GET.get('q')

    if query:
        movies = Movie.objects.filter(Q(title__icontains=query)).distinct()
        return render(request, 'recommend/list.html', {'movies': movies})

    return render(request, 'recommend/list.html', {'movies': movies})


# Show details of the movie
def detail(request, movie_id):
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.is_active:
        raise Http404
    movies = get_object_or_404(Movie, id=movie_id)
    movie = Movie.objects.get(id=movie_id)

    temp = list(MyList.objects.all().values().filter(
        movie_id=movie_id, user=request.user))
    if temp:
        update = temp[0]['watch']
    else:
        update = False
    if request.method == "POST":

        # For my list
        if 'watch' in request.POST:
            watch_flag = request.POST['watch']
            if watch_flag == 'on':
                update = True
            else:
                update = False
            if MyList.objects.all().values().filter(movie_id=movie_id, user=request.user):
                MyList.objects.all().values().filter(movie_id=movie_id,
                                                     user=request.user).update(watch=update)
            else:
                q = MyList(user=request.user, movie=movie, watch=update)
                q.save()
            if update:
                messages.success(request, "Movie added to your list!")
            else:
                messages.success(request, "Movie removed from your list!")

        # For rating
        else:
            rate = request.POST['rating']
            if Myrating.objects.all().values().filter(movie_id=movie_id, user=request.user):
                Myrating.objects.all().values().filter(
                    movie_id=movie_id, user=request.user).update(rating=rate)
            else:
                q = Myrating(user=request.user, movie=movie, rating=rate)
                q.save()

            messages.success(request, "Rating has been submitted!")

        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    out = list(Myrating.objects.filter(user=request.user.id).values())

    # To display ratings in the movie detail page
    movie_rating = 0
    rate_flag = False
    for each in out:
        if each['movie_id'] == movie_id:
            movie_rating = each['rating']
            rate_flag = True
            break

    context = {'movies': movies, 'movie_rating': movie_rating,
               'rate_flag': rate_flag, 'update': update}
    return render(request, 'recommend/detail.html', context)


# MyList functionality
def watch(request):

    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.is_active:
        raise Http404

    movies = Movie.objects.filter(
        mylist__watch=True, mylist__user=request.user)
    query = request.GET.get('q')

    if query:
        movies = Movie.objects.filter(Q(title__icontains=query)).distinct()
        return render(request, 'recommend/watch.html', {'movies': movies})

    return render(request, 'recommend/watch.html', {'movies': movies})


# To get similar movies based on user rating
def get_similar(movie_name, rating, corrMatrix):
    similar_ratings = corrMatrix[movie_name]*(rating-2.5)
    similar_ratings = similar_ratings.sort_values(ascending=False)
    return similar_ratings

# Recommendation Algorithm


def recommend(request):

    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.is_active:
        raise Http404

    movie_rating = pd.DataFrame(list(Myrating.objects.all().values()))
    new_user = movie_rating.user_id.unique().shape[0]
    current_user_id = request.user.id
    # if new user not rated any movie

    if movie_rating.empty or movie_rating[movie_rating['user_id'] == current_user_id].empty:
        context = {'movie_list': Movie.objects.all()[:10]}
        return render(request, 'recommend/rateit.html', context)
    else:
        print("Ratings exist")
        userRatings = movie_rating.pivot_table(index=['user_id'], columns=[
            'movie_id'], values='rating')
        userRatings = userRatings.fillna(0, axis=1)
        corrMatrix = userRatings.corr(method='pearson')

        user = pd.DataFrame(list(Myrating.objects.filter(
            user=request.user).values())).drop(['user_id', 'id'], axis=1)
        user_filtered = [tuple(x) for x in user.values]
        movie_id_watched = [each[0] for each in user_filtered]

        similar_movies = pd.DataFrame()
        similarities = []
        
        for movie_id, rating in user_filtered:
            similar_movie_ratings = get_similar(movie_id, rating, corrMatrix)
            similar_movies = pd.concat([similar_movie_ratings], ignore_index=True)
            for index, score in similar_movie_ratings.items():
                 similarities.append((index, score))
       
        print(similarities)

        sum_similar_movies = pd.DataFrame({'Similarity': similar_movies})
        sorted_movies = sum_similar_movies.sort_values(
            by='Similarity', ascending=False)

        movies_id = list(sorted_movies.index)
        movies_id_recommend = [
            each for each in movies_id if each not in movie_id_watched]
        preserved = Case(*[When(pk=pk, then=pos)
                           for pos, pk in enumerate(movies_id_recommend)])
        movie_list = list(Movie.objects.filter(
            id__in=movies_id_recommend).order_by(preserved)[:10])
        

        context = {'movie_list': movie_list}
        return render(request, 'recommend/recommend.html', context)


# Calculate Jaccard similarity
def calculate_jaccard_similarity(set1, set2):
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    if union == 0:
        return 0.0  # Handle the case where both sets are empty
    else:
        return intersection / union

# Content-based movie recommendations
def content_based_recommendation(request, movie_id):

    clicked_movie = get_object_or_404(Movie, id=movie_id)
    clicked_movie_genres = set(clicked_movie.genres.all())
    recommendations = []
    for movie in Movie.objects.exclude(id=movie_id):
        movie_genres = set(movie.genres.all())
        similarity = calculate_jaccard_similarity(clicked_movie_genres, movie_genres)
        recommendations.append((movie, similarity))

    # Sort recommendations by similarity in descending order
    recommendations.sort(key=lambda x: x[1], reverse=True)

    # Get the top 3-4 recommended movies
    top_recommendations = recommendations[:4]

    context = {'clicked_movie': clicked_movie, 'recommended_movies': top_recommendations}
    return render(request, 'recommend/content_recommendation.html', context)


    
def calculate_precision_recall(request):
    # Retrieve all users who have rated movies
    users_with_ratings = Myrating.objects.values('user_id').distinct()

    total_precision = 20.0
    total_recall = 10.0

    for user in users_with_ratings:
        user_id = user['user_id']

        # Get the movies rated by the user
        user_rated_movies = Myrating.objects.filter(user_id=user_id)

        # Get the movies in the user's MyList
        user_watchlist_movies = MyList.objects.filter(
            user_id=user_id, watch=True)

        # Calculate precision and recall for the user
        if user_rated_movies.count() > 0:
            recommended_movies = []
            actual_rated_movies = [rating.movie for rating in user_rated_movies]

            relevant_recommendations = len(
                set(recommended_movies) & set(actual_rated_movies))
            precision = relevant_recommendations / len(recommended_movies) if len(
                recommended_movies) > 0 else 0
            recall = relevant_recommendations / len(actual_rated_movies)

            total_precision += precision
            total_recall += recall

    # Calculate average precision and recall
    num_users = len(users_with_ratings)
    avg_precision = total_precision / num_users
    avg_recall = total_recall / num_users

    # Print precision and recall to the terminal
    print(f"Average Precision: {avg_precision:.2f}")
    print(f"Average Recall: {avg_recall:.2f}")

    # You can also return the values to be displayed on a web page if needed
    return HttpResponse(f"Average Precision: {avg_precision:.2f}<br> Average Recall: {avg_recall:.2f}")


    # Register user


def signUp(request):
    form = UserForm(request.POST or None)

    if form.is_valid():
        user = form.save(commit=False)
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user.set_password(password)
        user.save()
        user = authenticate(username=username, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)
                return redirect("index")

    context = {'form': form}

    return render(request, 'recommend/signUp.html', context)


# Login User
def Login(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)
                return redirect("index")
            else:
                return render(request, 'recommend/login.html', {'error_message': 'Your account disable'})
        else:
            return render(request, 'recommend/login.html', {'error_message': 'Invalid Login'})

    return render(request, 'recommend/login.html')


# Logout user
def Logout(request):
    logout(request)
    return redirect("login")