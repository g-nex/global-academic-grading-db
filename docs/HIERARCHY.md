# Hierarchy

Specified logical path:

```
University → Country → Faculty/Program → Degree Level → Academic Year → Grading Scheme
```

Country is a first-class table; `universities.country_iso2` is the foreign key so the graph is relationally normal for Postgres. Every distinct faculty/program, degree level, or year variant is a separate `scheme_id`.
