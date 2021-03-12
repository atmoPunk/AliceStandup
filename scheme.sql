persons(
	person_id: integer, primary key
	first_name: text, not null
	last_name: text
)

users(
	user_id: text, primary key
	standup_held: boolean, not null
	cur_speaker: integer, not null
)

teams(
	team_mapping_id: integer, primary key
	user_id: text, foreign key (users.user_id)
	person_id: integer, foreign key (persons.person_id)
)
