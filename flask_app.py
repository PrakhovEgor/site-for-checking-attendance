

from flask import Flask, session, redirect
from flask import render_template
from sqlalchemy import create_engine
from flask import request
import datetime

# Данные для дб
username = "########"
passwd = "########"
db_name = "########"
hostname = "########"
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key'

# Адрес дб
engine = create_engine("mysql://" + username + ":" + passwd + "@" + hostname + "/" + db_name + "?charset=utf8", pool_size=10,
                       max_overflow=20, echo=True)


@app.route("/", methods=['GET', 'POST'])
@app.route("/<activity>", methods=['GET', 'POST'])
def main(activity=""):
    if not session.get("user", False):
        return redirect("/login")
    if request.method == "POST":
        if "logout" in request.form:
            session.pop("user", default=None)
            return redirect("/login/" + activity)
        elif "admin" in request.form:
            return redirect("/adminpanel")
        elif "rate" in request.form:
            return redirect("/rating")
    return render_template('index.html', user=session.get("user")[0], score=get_score(session.get("user")[0]["login"]), data=get_user_activities(session.get("user")[0]["id"]))





@app.route("/login", methods=['GET', 'POST'])
@app.route("/login/", methods=['GET', 'POST'])
@app.route("/login/<activity>", methods=['GET', 'POST'])
def login(activity=""):
    if request.method == "POST":
        if "enter" in request.form:
            login = request.form["login"].strip()
            password = request.form["password"].strip()
            flag = 0
            if login == "" or password == "":
                flag = 1
            else:
                flag = 2
            connection = engine.connect()
            user_table = connection.execute("select * from auth_data where login = %s and password = %s", login,
                                            password)
            connection.close()
            user_data = [dict(row) for row in user_table]
            if user_data:
                session["user"] = user_data
                if login == "superadmin@140" and password == "superadmin@1395":
                    return redirect("/adminpanel")
                if activity:
                    return redirect("/activity/" + activity)
                else:
                    return redirect("/")
            return render_template("login.html", flag=flag, url=activity, defualt_login=login)
    return render_template("login.html", flag=0, url=activity)


@app.route("/register", methods=['GET', 'POST'])
@app.route("/register/", methods=['GET', 'POST'])
@app.route("/register/<activity>", methods=['GET', 'POST'])
def register(activity=""):
    if request.method == "POST":
        if "enter" in request.form:
            login = request.form["login"].strip()
            name = prep_name(request.form["name"])
            password_1 = request.form["password_1"].strip()
            password_2 = request.form["password_2"].strip()
            connection = engine.connect()
            flag = 0
            if login != "" and password_1 != "" and password_2 != "" and password_1 == password_2 and [dict(row) for row in connection.execute( # Проверка на наличие юзера в бд
                    "select * from auth_data where login = %s", login)] == []:
                connection = engine.connect()
                trans = connection.begin()
                connection.execute("INSERT INTO auth_data(login, name, password, score) VALUES (%s, %s, %s, %s)", (login, name, password_1, 0))
                trans.commit()
                connection.close()

                return redirect("/login/" + activity)
            else:
                if password_1 != "" and password_2 != "" and password_1.strip() != password_2.strip():
                    flag = 3
                elif [dict(row) for row in connection.execute(
                    "select * from auth_data where login = %s", login)] != []:
                    flag = 2
                else:
                    flag = 1
            return render_template("register.html", flag=flag, url=activity, default_login=login, default_name=name, debug=prep_name(request.form["name"]))
    return render_template("register.html", flag=0, url=activity)


@app.route("/adminpanel", methods=['GET', 'POST'])
def adminpanel():
    if session.get("user", [{"login": "skg"}])[0]["login"] != "superadmin@140":
        return redirect("/")
    if request.method == "POST":
        if "logout" in request.form:
            session.pop("user", default=None)
            return redirect("/login/")
        elif "prof" in request.form:
            return redirect("/")
        elif "rate" in request.form:
            return redirect("/rating")
        elif "add" in request.form:
            activity_name = " ".join(request.form["activity_name"].split())
            extra_text = request.form["extra_text"]
            timefrom = request.form["timefrom"] #+ datetime.timedelta(hours=3)
            timeto = request.form["timeto"] #+ datetime.timedelta(hours=3)
            flag = 0
            if activity_name.strip() == "":
                flag = 1
            else:
                if check_activity(activity_name):
                    flag = 2

                else:
                    add_activity(activity_name, timefrom, timeto, extra_text)
                    add_activity_to_archive(activity_name)


            return render_template("admin.html", flag=flag, data=get_activities())
        else:
            button_id = list(request.form.keys())[-1]
            connection = engine.connect()
            trans = connection.begin()
            connection.execute("DELETE FROM activity WHERE id=%s", (button_id))
            trans.commit()
            connection.close()
            return render_template("admin.html", flag=0, data=get_activities())
    return render_template("admin.html", flag=0, data=get_activities())


@app.route("/activity/<activity_url>", methods=['GET', 'POST'])
def activity(activity_url):
    activity = " ".join(activity_url.split('_'))
    if not session.get("user", False):
        return redirect("/login/" + activity_url)
    if not check_activity(activity):
        return redirect("/")
    status = ""
    flag = 0
    timefrom, timeto = get_activity_time(activity)
    if datetime.datetime.now() + datetime.timedelta(hours=3) < timefrom:
        flag = 1
        status = "Данное событие ещё не началось"
    elif timeto < datetime.datetime.now() + datetime.timedelta(hours=3):
        flag = 1
        status = "Данное событие уже закончилось"
    is_pressed = 0
    if check_visit(activity):
        is_pressed = 1
    if request.method == "POST":
        if "logout" in request.form:
            session.pop("user", default=None)
            return redirect("/login")
        elif "prof" in request.form:
            return redirect("/")
        elif "admin" in request.form:
            return redirect("/adminpanel")
        elif "rate" in request.form:
            return redirect("/rating")
        elif "enter" in request.form:
           if not check_visit(activity):
                add_activity_for_user(activity)
                give_score()
                is_pressed = 1
    return render_template('activity.html', activity=activity, is_pressed=is_pressed, flag=flag, extra_text=get_extra_text(activity), status=status, user=session.get("user")[0])


@app.route("/rating", methods=['GET', 'POST'])
def rating():
    if session.get("user", [{"login": "notadmin"}])[0]["login"] != "superadmin@140":
        return redirect("/")
    if request.method == "POST":
        if "logout" in request.form:
            session.pop("user", default=None)
            return redirect("/login/")
        elif "prof" in request.form:
            return redirect("/")
        elif "admin" in request.form:
            return redirect("/adminpanel")


    return render_template('rating.html', top=get_top())

def add_activity_for_user(activity):
    connection = engine.connect()
    trans = connection.begin()
    connection.execute("INSERT INTO user_activity(user_id, activity_id) VALUES (%s, %s)", (session.get("user")[0]["id"], get_activity_id(activity)))
    trans.commit()
    connection.close()


def add_activity(activity_name, timefrom, timeto, extra_text):
    connection = engine.connect()
    trans = connection.begin()
    connection.execute("INSERT INTO activity(name, timefrom, timeto, extra_text) VALUES (%s, %s, %s, %s)", (activity_name, timefrom, timeto, extra_text))
    trans.commit()
    connection.close()
    return


def add_activity_to_archive(activity_name):
    connection = engine.connect()
    table = connection.execute("select id from activity where name = %s", activity_name)
    connection.close()
    id = [dict(row) for row in table][0]["id"]

    connection = engine.connect()
    trans = connection.begin()
    connection.execute("INSERT INTO activity_archive(activity_id, activity_name) VALUES (%s, %s)", (id, activity_name))
    trans.commit()
    connection.close()
    return


def get_score(user):
    connection = engine.connect()
    user_table = connection.execute("select score from auth_data where login = %s", user)
    connection.close()
    score = [dict(row) for row in user_table][0]["score"]
    return score

def get_activities_names():
    connection = engine.connect()
    user_table = connection.execute("select name from activity")
    connection.close()
    activities_name = [list(dict(row).values()) for row in user_table]
    return activities_name


def get_activities():
    connection = engine.connect()
    user_table = connection.execute("select * from activity")
    connection.close()
    activities = [dict(row) for row in user_table]
    activities.sort(key=lambda x: x["timefrom"])
    for i in range(len(activities)):
        activities[i]["n"] = i + 1

        timefrom, timeto = activities[i]["timefrom"], activities[i]["timeto"]
        if datetime.datetime.now() + datetime.timedelta(hours=3) < timefrom:
            activities[i]["status"] = "Не началось"
        elif timeto < datetime.datetime.now() + datetime.timedelta(hours=3):
            activities[i]["status"] = "Закончилось"
        else:
            activities[i]["status"] = "Проходит"

        if activities[i]["extra_text"] == "":
            activities[i]["extra_text"] = "-"
        activities[i]["url"] = make_url(activities[i]["name"])

    return activities


def check_activity(activity):
    connection = engine.connect()
    user_table = connection.execute("select * from activity")
    connection.close()
    activities = [dict(row) for row in user_table]
    for i in activities:
        if i["name"] == activity:
            return True
    return False


def check_visit(activity):
    user = session.get("user", False)
    activity_id = get_activity_id(activity)
    if user:
        connection = engine.connect()
        user_table = connection.execute("select * from user_activity WHERE activity_id = %s", activity_id)
        connection.close()
        activities = [dict(row) for row in user_table]
        for i in activities:
            if i["user_id"] == user[0]["id"]:
                return True
        return False


def give_score():
    user = session.get("user")[0]
    connection = engine.connect()
    score = connection.execute("SELECT score FROM auth_data WHERE id = %s", (user["id"]))
    score = [dict(row) for row in score][0]["score"]
    connection.close()
    connection = engine.connect()
    trans = connection.begin()
    connection.execute("UPDATE auth_data SET score = %s WHERE id = %s", (score + 1, user["id"]))
    trans.commit()
    connection.close()


def get_activity_id(activity):
    connection = engine.connect()
    user_table = connection.execute("select * from activity")
    connection.close()
    activities = [dict(row) for row in user_table]
    for i in activities:
        if i["name"] == activity:
            return i["id"]
    return -1


def get_activity_time(activity):
    connection = engine.connect()
    user_table = connection.execute("select * from activity where name = %s", (activity))
    connection.close()
    activities = [dict(row) for row in user_table][0]
    return [activities["timefrom"], activities["timeto"]]


def prep_name(name):
    if name.strip():
        return " ".join([t.capitalize() for t in name.lower().split()])
    return ""


def make_url(activity_name):
    return "https://lyceumframe.pythonanywhere.com/activity/" + "_".join(activity_name.split())


def get_user_activities(user_id):
    connection = engine.connect()
    table = connection.execute("select * from user_activity WHERE user_id = %s", user_id)
    ids = [dict(row)["activity_id"] for row in table]
    activity_names = []
    for id in ids:
        res = connection.execute("select * from activity_archive WHERE activity_id = %s", id)
        temp = [dict(row) for row in res]
        if temp:
            activity_names.append([temp[0]["activity_name"], make_url(temp[0]["activity_name"])])
    connection.close()
    return activity_names


def get_extra_text(activity):
    connection = engine.connect()
    table = connection.execute("select extra_text from activity where name = %s", (activity))
    connection.close()
    text = [dict(row) for row in table][0]["extra_text"]
    return text

def get_top():
    connection = engine.connect()
    table = connection.execute("select * from auth_data")
    connection.close()
    user_data = [dict(row) for row in table]
    user_data.sort(key=lambda x: -x["score"])
    for i in range(len(user_data)):
        user_data[i]["n"] = i + 1
    return user_data




