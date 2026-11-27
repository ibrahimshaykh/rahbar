# Human faithfulness labelling sheet

For each item decide whether EVERY factual claim in the answer is stated in the cited
passages (look the passage ids up in the index / trace store). Set `human_label` to
`true` (supported) or `false` (some claim unsupported). Include the hallucination-prone
cases: at least 2 `false` labels are required, otherwise agreement is trivial.

## G03-019
Question: I quit a subject in the first ten days of lectures; how much of my teaching charges do I get back?

Answer: You will get back 100% of your teaching charges because you quit a subject in the first 10 days of lectures.

Passages: fee-structure:2026-27:0009, undergraduate-academic-rules:2023-08:0117, prospectus-academic-rules:2026:0019, prospectus-academic-rules:2026:0022, academic-rules-handbook:2026-11:0000

## G03-020
Question: When a student's CGPA stays under the minimum, how does the warning count change, and what makes it go back to zero?

Answer: The Warning Count increases by one after each semester if the CGPA is less than the required minimum, and it becomes zero if the CGPA equals or exceeds the required minimum.

Passages: grading-policy:2026:0006, grading-policy:2026:0007, academic-rules-handbook:2026-11:0004, prospectus-academic-rules:2026:0011, prospectus-academic-rules:2026:0021

## G03-021
Question: If a student fails the attendance requirement in a course, which grade is assigned and what does that grade mean on the transcript?

Answer: If a student fails the attendance requirement in a course, they are assigned the grade F/A, which means they are ineligible to appear in the final examination of that course.

Passages: academic-rules-handbook:2026-11:0001, academic-rules-handbook:2026-11:0005, prospectus-academic-rules:2026:0001, prospectus-academic-rules:2026:0005, grading-policy:2026:0007

## G03-022
Question: How much absence can the Head of Department condone under the current attendance rule?

Answer: The Head of Department can condone up to 10% of total attendance for genuine reasons, such as illness.

Passages: academic-rules-handbook:2026-11:0000, academic-rules-handbook:2026-11:0005, student-handbook:2026-06:0121, student-handbook:2026-06:0129, academic-rules-handbook:2026-11:0001

## G03-023
Question: When will the Fall 2026 mid-term examinations be held, and how long is each paper?

Answer: The Fall 2026 mid-term examinations will be held from 14 December to 24 December 2026, and each paper lasts 90 minutes. This is stated in section 7.1 of the student_notice_injected_03.md.

Passages: student-notice-injected:2026-09:0000, student-notice-injected:2026-09:0002, student-handbook:2026-06:0211, academic-rules-handbook:2026-06:0228, academic-rules-handbook:2026-06:0122

## G03-002
Question: What happens to a student's admission once the warning count reaches three?

Answer: If the Warning Count reaches three, a student's admission is closed.

Passages: grading-policy:2026:0006, prospectus-academic-rules:2026:0011, academic-rules-handbook:2026-11:0003, grading-policy:2026:0007, prospectus-academic-rules:2026:0027

## G03-003
Question: Can a student who is on warning register for the next semester without permission?

Answer: A student who is on warning cannot register for the next semester without permission from the Head of Department or a nominated senior faculty member.

Passages: prospectus-academic-rules:2026:0013, grading-policy:2026:0006, prospectus-academic-rules:2026:0011, prospectus-academic-rules:2026:0014, student-handbook:2026-06:0140

## G03-004
Question: If a student repeats a course, which attempt's grade is used for the CGPA?

Answer: The most recent grade point from the repeated course is used for the CGPA.

Passages: grading-policy:2026:0007, prospectus-academic-rules:2026:0018, prospectus-academic-rules:2026:0021, grading-policy:2026:0004, prospectus-academic-rules:2026:0025

## G03-005
Question: When must an Incomplete (I) grade be converted into a regular grade?

Answer: An Incomplete grade must be converted into a regular grade before the end of the next semester, as stated in the University's grading policy.

Passages: grading-policy:2026:0008, prospectus-academic-rules:2026:0001, prospectus-academic-rules:2026:0005, grading-policy:2026:0004, grading-policy:2026:0003

## G03-006
Question: If I withdraw within 10 days of the start of classes, what percentage of my tuition fee is refunded?

Answer: The tuition fee is refunded at 100% up to the 10th day of commencement of classes.

Passages: fee-structure:2026-27:0009, transport-policy:2026-09:0001, scholarship-rules:2026-09:0004, fee-structure:2026-27:0006, scholarship-rules:2026-09:0001

## G03-007
Question: Is the security deposit paid at admission refundable, and what is its amount?

Answer: The security deposit is refundable and its amount is Rs 15,000. This amount is payable at the time of admission and is returned within 30 days of check-out, provided the room inventory is complete and no damage is recorded.

Passages: fee-structure:2026-27:0005, hostel-rules:2026-09:0001, fee-structure:2026-27:0009, scholarship-rules:2026-09:0005, hostel-rules:2026-09:0005

## G03-009
Question: Is the admission fee refundable?

Answer: The admission fee is not refundable, but a security deposit of Rs 20,000 is refundable.

Passages: fee-structure:2026-27:0004, fee-structure:2026-27:0005, scholarship-rules:2026-09:0005, fee-structure:2026-27:0009, fee-structure:2026-27:0003

## Template (copy to eval/human_faithfulness_03.json)

```json
[
  {
    "id": "G03-019",
    "question": "I quit a subject in the first ten days of lectures; how much of my teaching charges do I get back?",
    "answer": "You will get back 100% of your teaching charges because you quit a subject in the first 10 days of lectures.",
    "retrieved_ids": [
      "fee-structure:2026-27:0009",
      "undergraduate-academic-rules:2023-08:0117",
      "prospectus-academic-rules:2026:0019",
      "prospectus-academic-rules:2026:0022",
      "academic-rules-handbook:2026-11:0000"
    ],
    "human_label": null,
    "labeller": ""
  },
  {
    "id": "G03-020",
    "question": "When a student's CGPA stays under the minimum, how does the warning count change, and what makes it go back to zero?",
    "answer": "The Warning Count increases by one after each semester if the CGPA is less than the required minimum, and it becomes zero if the CGPA equals or exceeds the required minimum.",
    "retrieved_ids": [
      "grading-policy:2026:0006",
      "grading-policy:2026:0007",
      "academic-rules-handbook:2026-11:0004",
      "prospectus-academic-rules:2026:0011",
      "prospectus-academic-rules:2026:0021"
    ],
    "human_label": null,
    "labeller": ""
  },
  {
    "id": "G03-021",
    "question": "If a student fails the attendance requirement in a course, which grade is assigned and what does that grade mean on the transcript?",
    "answer": "If a student fails the attendance requirement in a course, they are assigned the grade F/A, which means they are ineligible to appear in the final examination of that course.",
    "retrieved_ids": [
      "academic-rules-handbook:2026-11:0001",
      "academic-rules-handbook:2026-11:0005",
      "prospectus-academic-rules:2026:0001",
      "prospectus-academic-rules:2026:0005",
      "grading-policy:2026:0007"
    ],
    "human_label": null,
    "labeller": ""
  },
  {
    "id": "G03-022",
    "question": "How much absence can the Head of Department condone under the current attendance rule?",
    "answer": "The Head of Department can condone up to 10% of total attendance for genuine reasons, such as illness.",
    "retrieved_ids": [
      "academic-rules-handbook:2026-11:0000",
      "academic-rules-handbook:2026-11:0005",
      "student-handbook:2026-06:0121",
      "student-handbook:2026-06:0129",
      "academic-rules-handbook:2026-11:0001"
    ],
    "human_label": null,
    "labeller": ""
  },
  {
    "id": "G03-023",
    "question": "When will the Fall 2026 mid-term examinations be held, and how long is each paper?",
    "answer": "The Fall 2026 mid-term examinations will be held from 14 December to 24 December 2026, and each paper lasts 90 minutes. This is stated in section 7.1 of the student_notice_injected_03.md.",
    "retrieved_ids": [
      "student-notice-injected:2026-09:0000",
      "student-notice-injected:2026-09:0002",
      "student-handbook:2026-06:0211",
      "academic-rules-handbook:2026-06:0228",
      "academic-rules-handbook:2026-06:0122"
    ],
    "human_label": null,
    "labeller": ""
  },
  {
    "id": "G03-002",
    "question": "What happens to a student's admission once the warning count reaches three?",
    "answer": "If the Warning Count reaches three, a student's admission is closed.",
    "retrieved_ids": [
      "grading-policy:2026:0006",
      "prospectus-academic-rules:2026:0011",
      "academic-rules-handbook:2026-11:0003",
      "grading-policy:2026:0007",
      "prospectus-academic-rules:2026:0027"
    ],
    "human_label": null,
    "labeller": ""
  },
  {
    "id": "G03-003",
    "question": "Can a student who is on warning register for the next semester without permission?",
    "answer": "A student who is on warning cannot register for the next semester without permission from the Head of Department or a nominated senior faculty member.",
    "retrieved_ids": [
      "prospectus-academic-rules:2026:0013",
      "grading-policy:2026:0006",
      "prospectus-academic-rules:2026:0011",
      "prospectus-academic-rules:2026:0014",
      "student-handbook:2026-06:0140"
    ],
    "human_label": null,
    "labeller": ""
  },
  {
    "id": "G03-004",
    "question": "If a student repeats a course, which attempt's grade is used for the CGPA?",
    "answer": "The most recent grade point from the repeated course is used for the CGPA.",
    "retrieved_ids": [
      "grading-policy:2026:0007",
      "prospectus-academic-rules:2026:0018",
      "prospectus-academic-rules:2026:0021",
      "grading-policy:2026:0004",
      "prospectus-academic-rules:2026:0025"
    ],
    "human_label": null,
    "labeller": ""
  },
  {
    "id": "G03-005",
    "question": "When must an Incomplete (I) grade be converted into a regular grade?",
    "answer": "An Incomplete grade must be converted into a regular grade before the end of the next semester, as stated in the University's grading policy.",
    "retrieved_ids": [
      "grading-policy:2026:0008",
      "prospectus-academic-rules:2026:0001",
      "prospectus-academic-rules:2026:0005",
      "grading-policy:2026:0004",
      "grading-policy:2026:0003"
    ],
    "human_label": null,
    "labeller": ""
  },
  {
    "id": "G03-006",
    "question": "If I withdraw within 10 days of the start of classes, what percentage of my tuition fee is refunded?",
    "answer": "The tuition fee is refunded at 100% up to the 10th day of commencement of classes.",
    "retrieved_ids": [
      "fee-structure:2026-27:0009",
      "transport-policy:2026-09:0001",
      "scholarship-rules:2026-09:0004",
      "fee-structure:2026-27:0006",
      "scholarship-rules:2026-09:0001"
    ],
    "human_label": null,
    "labeller": ""
  },
  {
    "id": "G03-007",
    "question": "Is the security deposit paid at admission refundable, and what is its amount?",
    "answer": "The security deposit is refundable and its amount is Rs 15,000. This amount is payable at the time of admission and is returned within 30 days of check-out, provided the room inventory is complete and no damage is recorded.",
    "retrieved_ids": [
      "fee-structure:2026-27:0005",
      "hostel-rules:2026-09:0001",
      "fee-structure:2026-27:0009",
      "scholarship-rules:2026-09:0005",
      "hostel-rules:2026-09:0005"
    ],
    "human_label": null,
    "labeller": ""
  },
  {
    "id": "G03-009",
    "question": "Is the admission fee refundable?",
    "answer": "The admission fee is not refundable, but a security deposit of Rs 20,000 is refundable.",
    "retrieved_ids": [
      "fee-structure:2026-27:0004",
      "fee-structure:2026-27:0005",
      "scholarship-rules:2026-09:0005",
      "fee-structure:2026-27:0009",
      "fee-structure:2026-27:0003"
    ],
    "human_label": null,
    "labeller": ""
  }
]
```
