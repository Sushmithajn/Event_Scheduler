document.addEventListener('DOMContentLoaded', function() {
    const calendarEl = document.getElementById('calendar');
    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        events: '/events',
        eventClick: function(info) {
            if(confirm(`Delete event "${info.event.title}"?`)){
                fetch(`/delete/${info.event.id}`, {method: 'DELETE'})
                .then(() => calendar.refetchEvents());
            }
        }
    });
    calendar.render();

    document.getElementById('addEventBtn').addEventListener('click', () => {
        const title = document.getElementById('title').value;
        const description = document.getElementById('description').value;
        const date = document.getElementById('date').value;
        const time = document.getElementById('time').value;

        if(!title || !date){
            alert('Title and Date are required');
            return;
        }

        fetch('/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title, description, date, time})
        }).then(res => res.json())
          .then(data => {
              if(data.status === "success"){
                  calendar.refetchEvents();
                  document.getElementById('title').value = '';
                  document.getElementById('description').value = '';
                  document.getElementById('date').value = '';
                  document.getElementById('time').value = '';
              }
          });
    });

    document.getElementById('downloadPdf').addEventListener('click', () => {
        window.location.href = '/generate-pdf';
    });
});
