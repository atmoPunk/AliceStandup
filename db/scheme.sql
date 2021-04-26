CREATE TABLE USERS( -- пользователи навыка
	user_id TEXT PRIMARY KEY, -- user_id из навыка
	standup_held BOOLEAN NOT NULL,
	cur_speaker INTEGER NOT NULL
);

CREATE TABLE PERSONS( -- участники команд
	person_id SERIAL PRIMARY KEY,
	first_name TEXT NOT NULL,
	last_name TEXT,
	standup_organizer TEXT REFERENCES USERS(user_id),
	last_theme TEXT
);
