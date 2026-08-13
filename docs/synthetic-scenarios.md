# SehatRaasta Synthetic Scenarios

## Purpose

These scenarios define the expected behavior of the fictional-data prototype before application coding starts.


## Scenario 1: Complete for review

**Given** a fictional referral bundle exists  
**And** every expected category was reviewed  
**And** one category was deliberately marked `Not applicable`  

**When** the user opens the bundle status  

**Then** the app displays the bundle as `Ready for review`  
**And** the app identifies the category marked `Not applicable`  
**And** the app does not describe the referral or medical care as complete  

## Scenario 2: Pending test result

**Given** a fictional referral bundle exists  
**And** a test order exists  
**And** the test was performed  
**And** no result was received  

**When** the user opens the test status  

**Then** the app displays the status as `Pending`  
**And** the app does not display the status as `Completed`  
**And** the app does not display or invent a test result  

## Scenario 3: Invalid attachment

**Given** a fictional referral bundle exists  
**And** an unsupported or invalid attachment is available  

**When** the user attempts to upload the attachment  

**Then** the app rejects the attachment  
**And** the app displays a clear and safe error message  
**And** the app does not store the attachment  
**And** the existing bundle information remains unchanged  

## Scenario 4: Missing destination department

**Given** a fictional referral bundle exists  
**And** no destination department was entered  

**When** the user attempts to mark the bundle as `Ready for review`  

**Then** the app states that the destination department is required  
**And** the app does not mark the bundle as `Ready for review`  
**And** the existing bundle information remains unchanged  

## Scenario 5: Duplicate attachment

**Given** a fictional referral bundle exists  
**And** an attachment already exists in the bundle  
**And** a second file has the same SHA-256 value as the stored attachment  

**When** the user attempts to upload the second file  

**Then** the app rejects the second file as a duplicate  
**And** the app displays a clear and safe message  
**And** the app does not create a second attachment record  
**And** the original attachment remains unchanged  
**And** the existing bundle information remains unchanged  

## Scenario 6: Database error

**Given** a fictional referral bundle exists  
**And** the database cannot complete a save operation  

**When** the user attempts to save a valid change  

**Then** the app displays a safe message that the change was not saved  
**And** the app does not display passwords, paths, queries, or technical error details  
**And** the app does not report that the save succeeded  
**And** the existing stored information remains unchanged  
**And** the app records a safe audit event without clinical text  

## Domain rules

1. One fictional patient can have zero or many referral bundles.
2. Each referral bundle belongs to exactly one fictional patient.
3. One referral bundle can have zero or many child records in each supported category.
4. A test order and a test result are separate records.
5. A test result may link to its related test order.
6. A test order can remain pending without a result.
7. A document can exist while its related workflow remains pending.
8. Each transcribed clinical item must identify its source record.
9. The app must use `Source not supplied` when no source record exists.
10. Patient-entered information must not appear as clinician-reviewed information.
11. The app must not invent diagnoses, results, treatment advice, or clinical interpretations.
12. The app must not automatically translate clinical text.
13. The app must not mark a category `Not applicable` without a deliberate review decision.
14. Deleting an attachment must not delete or hide its audit-event history.
15. Audit events must not contain medical text or other sensitive content.
16. QR codes must not contain private medical information.
17. The development version must use fictional data only.


