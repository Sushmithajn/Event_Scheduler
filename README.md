# Event Scheduler

A simple web app to manage your events. Built with **Flask**, **SQLite**, and **JavaScript**. Users can register, login, add, view, edit, and delete events. You can also generate PDF reports and receive email reminders.

## Features

 User registration and login
 Add, edit, delete, and view events
 Generate PDF reports
 Email reminders for events

## Tech Stack

 **Backend:** Python, Flask
 **Database:** SQLite
 **Frontend:** HTML, CSS, JavaScript
 **PDF Generation:** ReportLab
 **Email:** SMTP
 **Scheduler:** APScheduler



## Installation

1. Clone the repo:
```bash
git clone https://github.com/Sushmithajn/Event_Scheduler.git
cd Event_Scheduler


## Create a virtual environment and activate it:

python -m venv myenv
myenv\Scripts\activate  # Windows
# source myenv/bin/activate  # macOS/Linux

## Install dependencies:

pip install -r requirements.txt

##Run the App
python app.py
