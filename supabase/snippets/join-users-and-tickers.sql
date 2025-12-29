SELECT *
FROM users u
  INNER JOIN watchlists w on u.id = w.user_id
  INNER JOIN entities e on w.entity_id = e.id;