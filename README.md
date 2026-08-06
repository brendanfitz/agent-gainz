# agent-gainz

An agentic, data-driven personal trainer that reviews recent workout performance and provides evidence-backed guidance for the workout immediately ahead.

The system is designed to run before training, such as during a morning check-in. It combines historical workout data, today’s prescribed program, targeted readiness questions, and deterministic training analytics to recommend where to push, maintain, or pull back.

## 1. Project Goal

Build an AI personal trainer that prepares the user for the next workout.

The system should:

* Summarize the most recent workout
* Review relevant historical performance
* Analyze the exercises prescribed for today
* Compare today’s plan with previous performances of those exercises
* Recommend where to push, maintain, or pull back
* Ask follow-up questions when recovery or readiness information is missing
* Explain the evidence behind each recommendation
* Record feedback for future evaluation

The project will combine:

* Workout analytics
* Data engineering
* Agentic AI workflows
* Structured outputs
* Recommendation evaluation
* Longitudinal performance tracking

## 2. Primary User Experience

The user runs `agent-gainz` before beginning a workout.

The system reviews:

1. The most recently completed workout
2. Recent performance trends
3. Today’s prescribed workout
4. Historical performance for today’s exercises
5. Available readiness information
6. Notes or data-quality issues that may affect the analysis

It then produces a pre-workout briefing with:

* A summary of the previous workout
* A preview of today’s session
* Key performance observations
* Targeted readiness questions
* Exercise-specific recommendations
* Important limitations or uncertainties
* An optional training tip

## 3. Example Pre-Workout Workflow

```text
Load workout data
        |
        v
Identify the latest completed workout
        |
        v
Identify today's prescribed workout
        |
        v
Analyze recent and historical performance
        |
        v
Ask readiness questions
        |
        v
Generate today's workout recommendations
        |
        v
Complete the workout
        |
        v
Record performance and feedback
```

An example briefing might include:

> Your previous upper-body session showed improved pressing volume, but performance declined during the final working sets of Flat DB Press.

> Today’s workout includes Flat DB Press again. Based on your recent performance, begin with the prescribed load and target the upper end of the rep range only if the first working set is completed within the planned effort level.

## 4. Repository Structure

The project will use two repositories.

### `agent-gainz`

Responsible for:

* Loading workout data for the MVP
* Identifying previous and upcoming workouts
* Calculating workout comparisons
* Running the OpenAI Agents SDK
* Generating pre-workout briefings
* Asking readiness questions
* Producing recommendations
* Validating agent output
* Evaluating recommendation quality
* Providing the user interface

### Data Platform Repository

Responsible for:

* Ingesting Excel workout logs
* Loading data into PostgreSQL
* Cleaning and transforming workout data
* Running dbt models and tests
* Orchestrating the pipeline with Airflow
* Producing analytical tables for `agent-gainz`

## 5. MVP Architecture

The MVP will use the parsed Excel dataframe directly.

```text
Excel Workout Log
        |
        v
Parsed DataFrame
        |
        v
Previous Workout and Today's Plan
        |
        v
Deterministic Workout Analytics
        |
        v
OpenAI Coach Agent
        |
        v
Pre-Workout Briefing
```

PostgreSQL, dbt, and Airflow will be added after the first analytical and agentic workflow is working.

## 6. MVP Data Source

The primary MVP dataset is `df_parsed`.

It contains one row per programmed exercise within a workout.

Important fields include:

* Workout date
* Program day
* Exercise
* Prescribed warm-up sets
* Prescribed working sets
* Prescribed rep range
* Prescribed RPE
* Prescribed rest
* Substitute exercises
* Logged load
* Top weight
* Repetitions at the top weight
* Total repetitions
* Volume load
* Drop-set information
* Workout notes
* Parsing and inference metadata

The workout date and program day identify the same workout.

For completed workouts, the dataframe contains both prescribed and logged performance data.

For the workout ahead, the dataframe contains the prescribed fields but does not yet contain logged performance.

## 7. Identifying Workout State

Each workout should be classified as one of the following:

### Completed

The workout contains sufficient logged performance data to analyze what occurred.

### Upcoming

The workout contains prescribed programming but no completed performance data.

### Partially Completed

The workout contains some logged performance but is incomplete.

The MVP should identify:

* The latest completed workout
* The next upcoming workout

The system should not generate a pre-workout recommendation from a partially completed session unless that use case is explicitly supported later.

## 8. Role of the Sets DataFrame

The `sets` dataframe is optional for the MVP.

The exercise-level dataframe already supports:

* Previous workout summaries
* Exercise comparisons
* Top-weight comparisons
* Rep comparisons
* Volume comparisons
* Drop-set identification
* Basic progression signals
* Analysis of today’s prescribed exercises

The per-set dataframe may be added later for:

* Set-by-set performance analysis
* Within-exercise fatigue
* First-set versus final-set comparisons
* Exact rep progression
* Shorthand validation
* More detailed data-quality checks

## 9. MVP Analytics

The first version should calculate a focused set of reliable metrics.

### Previous Workout Summary

* Number of exercises
* Number of working sets
* Number of drop sets
* Total repetitions
* Exercises performed
* Exercises with notes
* Exercises with changing weights
* Meaningful improvements or regressions

### Today’s Workout Preview

* Exercises prescribed
* Warm-up and working-set prescriptions
* Prescribed rep ranges
* Prescribed RPE ranges
* Prescribed rest periods
* Superset structure
* Available substitutions
* Notes attached to the workout

### Exercise History

For each exercise prescribed today:

* Find its most recent completed appearances
* Compare top weight
* Compare repetitions at the top weight
* Compare total repetitions
* Compare volume load
* Identify whether performance is improving, stable, or declining
* Identify whether the exercise is new
* Identify whether there is insufficient history

### Progression Signals

Potential signals include:

* Top weight increased
* Repetitions increased at the same weight
* Volume increased
* Volume decreased
* Prescribed rep range was missed
* Exercise performance has been stable
* Exercise performance has recently declined
* New exercise
* Drop set added
* Unusual load change
* Insufficient comparison history

### Data-Quality Signals

* Inferred sets
* Missing values
* Unusual load strings
* Bodyweight exercises
* Exercise-name inconsistencies
* Notes that may require clarification
* Upcoming rows that appear to contain logged values
* Completed rows that appear to be missing logged values

## 10. Readiness Check-In

Before generating recommendations, the agent may ask a small number of targeted questions.

Potential topics include:

* Sleep quality
* General energy
* Muscle soreness
* Joint discomfort
* Motivation
* Whether the user is following the prescribed workout as written
* Whether equipment or exercise substitutions will be necessary

The agent should ask only questions whose answers could materially change the recommendation.

The MVP should ask no more than three questions.

## 11. Agent Design

The MVP will use the OpenAI Agents SDK.

It will begin with one coach agent.
<!-- 
Claude, I have one coach agent written here, but I am open to multiple agents
Decide which is cleaner
-->

The coach agent will:

* Request workout analytics through tools
* Summarize the previous workout
* Review the workout immediately ahead
* Interpret recent exercise trends
* Ask targeted readiness questions
* Generate exercise-specific recommendations
* Explain confidence and limitations
* Avoid unsupported medical claims
* Record recommendation feedback

The agent will not calculate metrics directly from raw dataframe rows.

## 12. Agent Tools

Initial tools may include:

* Get the latest completed workout
* Get the upcoming prescribed workout
* Summarize the previous workout
* Compare today’s exercises with prior workouts
* Get progression signals
* Get data-quality issues
* Record readiness responses
* Record recommendation feedback

These tools will return structured data.

## 13. Agent Output

The pre-workout briefing should contain the following sections.

### Previous Workout Summary

A concise description of the latest completed workout.

### Today’s Workout

A concise preview of the prescribed session.

### Key Observations

No more than three meaningful findings from recent performance or today’s programming.

### Readiness Questions

No more than three questions that could affect the recommendations.

### Recommendations

Recommendations should be directly relevant to the workout ahead.

Each recommendation should include:

* Suggested action
* Exercise or workout area
* Supporting evidence
* Confidence level
* Whether user confirmation is required

### Limitations

Any important data constraints, missing context, or uncertainty.

### Optional Tip

A short training tip or bodybuilding fact that has not been shown recently.

## 14. Recommendation Categories

The MVP should keep recommendations conservative and immediately actionable.

### Push

Examples include:

* Target the upper end of the prescribed rep range
* Consider a small load increase
* Add repetitions before adding weight
* Continue the planned progression
* Use a more challenging prescribed variation

### Maintain

Examples include:

* Repeat the most recent working weight
* Stay near the middle of the prescribed rep range
* Maintain the current volume
* Follow the program as written
* Gather another comparable workout before progressing

### Pull Back

Examples include:

* Avoid increasing load today
* Begin at the lower end of the prescribed rep range
* Reduce the working weight if the warm-up feels unusually difficult
* Choose a listed substitute
* Avoid adding optional volume

### Ask for Context

Examples include:

* Clarify soreness or joint discomfort
* Clarify sleep or recovery
* Confirm an unusual historical load entry
* Confirm whether an exercise substitution is planned
* Clarify a note from the workout log

## 15. Recommendation Guardrails

The agent should not automatically rewrite the program.

Recommendations should generally remain within the existing prescription.

For example, the agent may recommend:

* Which end of the rep range to target
* Whether to repeat or slightly increase a prior load
* Whether to begin conservatively
* Whether to use a prescribed substitution
* Which exercise deserves particular attention

The agent should not:

* Add large amounts of unplanned volume
* Recommend large load increases without strong evidence
* Diagnose injuries
* Recommend training through acute pain
* Replace the full workout without user approval
* Claim that prescribed RPE was the actual experienced RPE

## 16. MVP Development Phases

### Phase 1: Data Validation

* Load `df_parsed`
* Confirm required columns
* Normalize exercise names
* Validate workout dates and program days
* Classify workouts as completed, upcoming, or partial
* Identify the latest completed workout
* Identify the next upcoming workout
* Add tests for bodyweight and inferred data

### Phase 2: Deterministic Analytics

* Build the previous workout summary
* Build the upcoming workout preview
* Compare today’s exercises with historical performance
* Generate progression signals
* Generate data-quality signals
* Produce a pre-workout report without an LLM

### Phase 3: OpenAI Agent

* Add analytical tools
* Add the coach agent
* Add structured output
* Add readiness questions
* Add recommendation confidence
* Enable tracing
* Generate the first agent-produced pre-workout briefing

### Phase 4: Feedback and Evaluation

* Record the agent’s recommendations
* Record whether each recommendation was followed
* Compare the recommendation with the completed workout
* Collect a usefulness rating
* Create representative workout test cases
* Check factual accuracy
* Check that recommendations cite evidence
* Check that numerical claims match tool output
* Check for unsupported medical or injury claims

### Phase 5: Data Platform

* Create the data-platform repository
* Load Excel data into PostgreSQL
* Build dbt staging and mart models
* Add dbt tests
* Add Airflow orchestration
* Replace the dataframe adapter with a PostgreSQL adapter

## 17. Future Enhancements

Potential later additions include:

* Per-set analysis
* Actual RPE tracking
* Sleep, soreness, and readiness history
* Expected-performance modeling
* Anomaly detection
* Change-point detection
* Recommendation calibration
* Program adherence analysis
* Tip-of-the-day history
* Personalized exercise substitutions
* Recommendation outcome analysis
* LangGraph implementation comparison
* CrewAI experiment
* Web or mobile interface
* Post-workout check-in
* Automated next-morning briefing

## 18. Immediate Next Steps

1. Create the `agent-gainz` repository.
2. Add the Excel dataframe loader.
3. Define completed, upcoming, and partial workout logic.
4. Build the previous workout summary.
5. Build the upcoming workout preview.
6. Compare today’s exercises with historical performance.
7. Produce a deterministic pre-workout report.
8. Define the structured agent output.
9. Wrap the analytics functions as OpenAI Agents SDK tools.
10. Generate the first pre-workout briefing.