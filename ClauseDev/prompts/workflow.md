Legislative Bill Analysis System
Current Data
JSON of every bill (Passed or Failed) from 2009 to 2026
MVP Dataset (2019-2026)
Each bill entry contains:

Title + Description → Combined as Bill Text
Committee Votes → Separated into Senate and Assembly (numerical)
Outcome → Numerical stages (0 = failed first step, 1 = failed second step, 2 = vetoed, 3 = passed)

Sample Structure:

    {

        "Bill Title": "..."

        "Bill Description": "..."

        "Full Bill Text": "..."

        "Date Passed": "..."

        "Votes": {

            "Senate": [23, 17],

            "Assembly": [67, 13]

        }

        "Stage Passed": 2

    }

Dataset Balance:

Basic: 12 passed, 11 failed
Detailed: 5 passed with 90%+ support, 7 narrow passes, 8 vetoed, 3 failed first step
User Workflow
Step 1: Jurisdiction Check & Formatting Validation
The user uploads their draft bill and specifies jurisdiction. For local bills, they can optionally upload a sample bill from their jurisdiction. If no sample is provided, the system warns them that formatting validation will be limited.

The system checks if the bill follows proper formatting conventions by comparing it against the dataset. For California (brute force approach for MVP), this means matching structural elements: enacting clause (mandatory), section numbering, citation style, amendment language, and standard clauses.

Technical: Direct string pattern matching against jurisdiction templates stored in dataset. Parse the uploaded bill into sections, extract formatting markers (section headers, numbering schemes, legal citations), and compare against known patterns from passed bills in that jurisdiction. Flag discrepancies with severity levels.
Step 2: Similar Bill Retrieval
The system finds bills in the dataset that are topically similar to the user's draft. This happens in two filtering stages.

First, the system uses the bill's title and one-sentence summary to filter from 20,000 bills down to 200-400 candidates. This uses keyword matching (KeyBert), simple embedding models, or ML heuristics with clustering to identify topical similarity.

Second, the system loads the full text of these 200-400 bills and uses a stronger embedding model or small LLM to narrow down to the top 30 most similar bills. The final 30 are balanced 50-50 between passed and failed bills so the LLM has sufficient data to compare language patterns between successful and unsuccessful legislation.

Technical: Stage 1 uses lightweight keyword extraction or sentence embeddings (like MiniLM) on titles/summaries, with cosine similarity ranking. Stage 2 loads full text for top candidates, runs denser embeddings or small classification model to score semantic similarity, then applies stratified sampling to ensure 15 passed and 15 failed bills in final set.
Step 3: Language Pattern Extraction
The LLM analyzes the 30 similar bills alongside the user's draft to identify parallel structural elements: citations, exemptions, definitions, enforcement mechanisms, prohibition/requirement sections, findings and declarations, and other core provisions.

The goal is to compare how successful bills, unsuccessful bills, and the user's draft bill structure these elements. The system identifies what structures are present in passed bills but missing or weak in the user's draft, and what structures in failed bills the user should avoid.

Technical: Prompt LLM to extract specific section types from each bill using few-shot examples. Create structured comparison showing which provisions appear in passed vs failed bills, their typical placement and language patterns. Generate differential analysis highlighting gaps in user's draft compared to successful bills.
Step 4: Legal Conflict Analysis
The system performs two types of checks: external law conflicts and constitutional issues.

For external conflicts, the LLM identifies potential legal barriers across three categories:

Federal Preemption: Does federal law prohibit states/cities from regulating this topic? (Example: cities cannot regulate immigration as it falls under federal authority)

State Preemption (for local bills): Does state law prohibit cities from regulating this topic? (Example: some states prohibit cities from banning plastic bags)

Conflicting Laws: Does this contradict existing laws in the same jurisdiction? (Example: new law bans X while old law requires X)

The LLM reasons about possible intersecting laws, then uses a legal database fetch tool to retrieve the actual text of potentially conflicting statutes. It pinpoints exact sections of the drafted bill that conflict with existing law, citing the specific conflicting statutes.

For constitutional checks, the LLM evaluates five areas without external tools:

Commerce Clause: Does this restrict interstate commerce unconstitutionally? Takings Clause: Does this require compensation for property taken? Equal Protection: Does this treat similar entities differently without justification? Due Process: Does this provide fair notice and hearing procedures? First Amendment: Does this restrict speech/religion unconstitutionally?

All conflicts are tagged with risk levels: HIGH (constitutional conflict, likely immediate rejection), MEDIUM (preemption disagreements or statutory conflicts), LOW (minor misalignments with conventions).

Technical: LLM generates hypotheses about conflicting laws based on bill content and jurisdiction. Use legal database API or web search to fetch suspected conflicting statutes. Run pattern matching to identify contradictory language between user bill and fetched laws. For constitutional analysis, use prompted reasoning with legal frameworks. Output structured conflict report with specific section citations and risk ratings.
Step 5: Stakeholder & Opposition Analysis
Using the language patterns from Step 3, the system identifies shortcomings in how the bill addresses affected industries and stakeholders. This includes analyzing scope issues like targeting "companies that use fossil fuels" (too broad, includes PG&E) versus "companies that extract fossil fuels" (better, more specific).

The LLM uses a web search tool to research which specific companies and industries would oppose the bill based on its provisions. It identifies the key stakeholders affected and their likely positions.

The system then suggests language changes that accomplish the bill's core goals while reducing opposition:

Mitigation through gradual implementation: Phase-in periods, allowing materials under 20% plastic threshold, grandfather clauses for existing operations

Refined definitions: Narrowing industry scope to affect fewer organizations while maintaining core impact

For complex rewording, the base LLM can call a stronger reasoning model (like Claude 3.5 Sonnet calling Claude Opus) to generate alternative formulations.

Each suggested change includes basic statistics on tradeoffs (estimated number of entities affected, implementation timeline, enforcement costs) so users can easily compare options and decide whether to accept them.

Technical: Parse bill provisions to extract affected entity types. Use web search API to find major organizations in those categories and their policy positions. Identify opposition patterns from similar bills in dataset. Generate alternative language formulations that `narrow scope while preserving intent. For complex rewording, chain LLM calls where base model identifies what needs changing and stronger model generates alternatives. Calculate impact metrics by comparing entity counts and implementation parameters across original vs suggested language.
Step 6: Structural Improvement Suggestions
Using the extracted patterns from Step 3 and formatting requirements from Step 1, the system compares the user's draft against passed bills and jurisdiction formatting standards. Every section of the draft receives structured feedback.

For each section, the system provides:

The exact language the user wrote in their draft
Contrasting language from passed bills, with at least one concrete example
Reasoning explaining why the passed bill structure is more effective
Formatting corrections to match jurisdiction standards

The LLM determines which sections of which passed bills correspond to each section of the user's draft, enabling precise, relevant comparisons. This requires good prompting with specific retrieval tools that can pull the right sections from the right bills.

The enacting clause is mandatory and flagged immediately if missing, no AI analysis needed.

Technical: Section-level alignment between user draft and the 30 similar bills from Step 2. Use LLM to classify each section by type (definitions, prohibitions, enforcement, etc), then retrieve matching sections from passed bills. Generate side-by-side comparisons with specific examples. Apply jurisdiction formatting rules as hard constraints. Use web search for any supplementary research on legislative best practices or jurisdiction-specific requirements.
Step 7: Final Review & Download
The system presents a complete summary of all changes made to the user's bill, organized by category: legal fixes, strategic tradeoffs, and writing updates. Each change is marked as either applied or kept as the user's original version.

The user sees an updated risk level showing improvement from their original draft. A prominent download button provides the updated bill with all accepted changes incorporated. The user can view the full bill text with color-coded edits and explanations for each change before downloading.

Options to start over with a new bill or export a detailed change log are available.

Technical: Aggregate all modifications from Steps 1-6 into a structured change manifest. Apply accepted changes to the original bill text, preserving rejected suggestions as comments or metadata. Generate color-coded diff views using simple text comparison (insertions in green, deletions in red, with hover explanations). Recalculate risk score based on remaining issues. Export final bill as formatted document (PDF/DOCX) with optional change tracking enabled. Store session data for potential revision iterations.

PHASE 1:
STEP 1: Identify Purpose & Jurisdiction
What user provides at start:
Jurisdiction type: Local / State / Federal
Specific location: "California" or "San Francisco" or "United States"
Policy goal: Free text description (e.g., "Ban single-use plastics in grocery stores")
(Optional) If local bill: Upload a sample passed bill from that city to copy format
What AI does:
Determines bill structure requirements based on jurisdiction:
Local → Ordinance format
State → State-specific format (California is different from New York)
Federal → Congressional bill format
Loads correct template:
Required sections (what MUST be included)
Enacting clause (legal opening phrase)
Citation style (how to reference other laws)
Formatting rules (numbering, capitalization, etc.)
If local + no sample uploaded → warns user that format might not match their city exactly
Why this matters:
A California state bill has different requirements than a San Francisco local ordinance
Each jurisdiction has specific legal language that MUST be included
Wrong format = bill gets rejected immediately
Output to user:
"Your bill will be formatted as a [California State Bill / San Francisco Ordinance / Federal Bill]"
"Required sections: [list]"
"We'll search for similar bills to use as templates..."

STEP 2: Find Similar Bills (Historical Research)

What AI does:
Takes user's policy goal and classifies it into topic categories:
Environmental, Healthcare, Housing, Criminal Justice, etc.
Searches bill database for similar bills:
Same topic
Across ALL jurisdictions (all 50 states, federal, major cities)
Both PASSED and FAILED bills
Finds 20-50 similar bills
Ranks them by relevance (how similar to user's goal)
Separates into passed vs. failed
What AI analyzes:
How many similar bills passed vs. failed
Which states passed them, which states failed
Vote counts (close votes vs. landslide votes)
What specific provisions were included in passed bills
What provisions were in failed bills
Why this matters:
Don't reinvent the wheel - use language that already worked
Avoid patterns that cause bills to fail
Learn from other states' successes and mistakes
Output to user:
"We found 23 similar bills:
- 12 passed (California, Oregon, Washington, New York, Colorado, etc.)
- 11 failed (Texas, Florida, Arizona, etc.)

Key insight: Bills that included retail exemptions for small stores passed 2x more often (10 of 12 passed bills had this, only 2 of 11 failed bills had it)

Key insight: Bills with 12-month phase-in periods passed 3.4x more often

Warning: Bills with immediate enforcement (no grace period) failed 9x more often - avoid this"

STEP 3: Extract & Adapt Useful Language
What AI does:
Takes the top 5-10 most relevant bills
Extracts specific sections from each:
How they defined key terms (Definitions section)
What restrictions/requirements they imposed (Core provisions)
Which agency enforced it (Enforcement mechanism)
How violations were penalized (Penalty structure)
How much it cost (Fiscal impact)
What timeline they used (Phase-in period)
Adapts language from source jurisdiction to user's jurisdiction:
Changes agency names (e.g., "Oregon Environmental Quality Commission" → "California Air Resources Board")
Changes legal citations (e.g., "Oregon Revised Statutes § 123" → "California Health and Safety Code Section 456")
Keeps the legal precision while making it fit user's location
Example:
From: California AB-888 (PASSED)
Original text: "This section shall not apply to retail establishments with less than 5,000 square feet, as defined in California Retail Code Section 12345."

Adapted to: Oregon
New text: "This section shall not apply to retail establishments with less than 5,000 square feet, as defined in Oregon Business Code Section 67890."3

Why we're borrowing this: wCalifornia's retail exemption was in a bill that PASSED. Same language worked there, likely to work in Oregon.
Why this matters:
Professional bills use precise legal language
Copying from successful bills = higher chance of success
Must adapt to user's jurisdiction or it's invalid (checking agency names and groups in local context)
Output to user:
"We're using language from California AB-888 (passed) for your retail exemption clause"
"We're using enforcement mechanism from Washington SB-200 (passed)"
Shows original vs. adapted text
“PHASE 1 Complete…PHASE 2 Loading”

PHASE 2: DRAFTING
STEP 4: Draft Definitions Section
What AI does:
Prompts user for existing definitions that can be entered (if they have it ready)
OR
Identifies key terms that need legal definitions:
Who/what does the bill regulate?
What actions are prohibited/required?
What exemptions exist?
For each term, generates 2-3 definition options:
Narrow definition (affects fewer entities)
Broad definition (affects more entities)
Medium definition (compromise)
For each option, estimates:
How many entities affected
Political feasibility (likelihood of passing)
Who would oppose it
CRITICAL USER DECISION: User must choose definition scope at start (or enter current definition and get recommendations or changes) - this determines who the bill affects
Example:
Term to define: "Fossil fuel company"

Option 1 - NARROW (AI recommends this):
"Any entity primarily engaged in the extraction, refining, or sale of coal, petroleum, or natural gas"
- Affects: ~500 companies (oil/gas extraction companies only)
- Excludes: Utilities like PG&E that burn fossil fuels for electricity
- Political feasibility: HIGH - won't anger utility companies or their workers
- Who opposes: Oil/gas industry only

Option 2 - BROAD:
"Any entity that extracts, refines, sells, OR uses fossil fuels for commercial energy generation"
- Affects: ~5,000 companies (includes all power plants, utilities)
- Includes: PG&E and all major utilities
- Political feasibility: LOW - utilities will lobby against this hard
- Who opposes: Oil/gas industry + utility companies + utility worker unions
- Warning: In California, this would likely fail because PG&E is critical infrastructure

AI Recommendation: Use Option 1 (narrow). Including utilities has caused 8 of 11 similar bills to fail.
Why this matters:
Definitions determine who the bill affects
Too broad = powerful opposition = bill fails
Too narrow = bill doesn't achieve goal
This is where strategic thinking matters most
Output to user:
Shows 2-3 definition options for each key term
Explains trade-offs (scope vs. political feasibility)
Makes recommendation based on historical data
User chooses which definitions to use
STEP 4.5: Draft Core Provisions (The Substance)
What this is:
The actual substantive sections that define what the bill DOES
What is prohibited, required, or regulated
Who must comply with the law
What exemptions or carve-outs exist
Under what conditions/circumstances the law applies
Why bills fail without this:
"All scaffolding, no substance" - bill has definitions and enforcement but no actual requirements
Without clear prohibitions/requirements, no one knows what the law actually does
Vague core provisions = agencies can't enforce, courts can't interpret
Missing exemptions = opposition kills the bill
What AI does:
Assembles core provisions from extracted language (Step 3):
Takes successful bill provisions identified in Step 2-3
Adapts language to user's jurisdiction
Structures into numbered sections (Section 301, 302, etc.)
Applies definition scope chosen in Step 4
Generates primary prohibition/requirement section:
Main "shall" or "shall not" language
Clear statement of what entities must do or not do
References definitions from Step 4
Uses proven language patterns from passed bills
Creates exemption subsections:
Standard exemptions from similar successful bills
Common carve-outs that reduced opposition
Structured as (b) subsection with numbered list
Leaves room for strategic additions from Step 5
Adds supporting requirement sections (if applicable):
Alternative compliance options
Standards/specifications (e.g., "reusable bag requirements")
Transition provisions
Special circumstances
Cross-references definitions and other sections:
Links to Section definitions ("as defined in Section 201")
References effective dates
Ensures internal consistency
Example:
PART 3: PROHIBITIONS AND REQUIREMENTS
Section 301: Prohibition on Single-Use Plastic Bags
(a) No retail establishment, as defined in Section 201(d), shall provide single-use plastic carryout bags to customers at the point of sale.
(b) Exemptions. This section does not apply to:
    (1) Retail establishments with a physical sales area of less than 5,000 square feet, as measured by the interior floor space available for customer transactions;
        [Source: California SB-270 (PASSED) - this exemption appeared in 10 of 12 passed bills]
    (2) Bags provided for any of the following purposes:
        (i) Packaging of unwrapped produce, bulk items, meat, or fish
        (ii) Prescription medications dispensed by a pharmacy
        (iii) Newspapers or dry cleaning
        [Source: Washington SB-5323 (PASSED) - these exemptions reduced retail opposition]
    (3) Nonprofit charitable reusers as defined in Section 201(e)
        [Source: Oregon HB-2509 (PASSED) - protected Goodwill/food banks from opposition]
(c) Restaurant takeout and delivery orders are subject to this prohibition.
    [Source: San Francisco Ordinance 140-07 (PASSED) - closing common loophole]
Section 302: Reusable Bag Standards
(a) Retail establishments may provide reusable bags at the point of sale that meet the following minimum standards:
    (1) Have a minimum lifetime capability of 125 uses carrying 22 pounds over a distance of 175 feet;
    (2) Are machine washable or made from material that can be cleaned or disinfected; and
    (3) Are either:
        (i) Made from cloth or other washable fabric; or
        (ii) Made from recycled plastic film with recycled content of at least 40 percent
    [Source: California SB-270 standards - passed legislative review, industry-accepted]
(b) Retail establishments may charge customers a reasonable fee for reusable bags provided under this section.
Section 303: Paper Bag Standards
(a) Retail establishments may provide paper carryout bags at the point of sale that meet the following standards:
    (1) Contain a minimum of 40 percent post-consumer recycled content;
    (2) Display the words "Reusable and Recyclable" in a highly visible manner on the outside of the bag
    [Source: Multiple passed bills - this language survived legal challenges]
(b) Retail establishments shall charge customers not less than ten cents ($0.10) for each paper carryout bag provided.
    [Source: Fee requirement reduced "bag hoarding" behavior in 8 of 10 jurisdictions]
(c) All monies collected pursuant to subdivision (b) may be retained by the retail establishment.
    [Source: Revenue retention = no retail opposition in 11 of 12 passed bills]
(Note: AI generated these sections by combining provisions from California SB-270, Washington SB-5323, and Oregon HB-2509, all of which PASSED. User should review exemptions and may add more based on Step 5 strategic recommendations.)
Why this matters:
This is the actual LAW - everything else supports these core sections
Step 6.6 enforcement references these section numbers ("violates Section 301")
Step 6.7 fiscal provisions calculate costs based on what's required here
Courts interpret ambiguous terms using these core provisions
Without clear core provisions, agencies won't know what to enforce
Output to user:
Complete numbered core provisions
Shows which successful bill each provision came from
Explains why specific language/exemptions were included
Highlights areas where user may want to adjust based on policy goals
User reviews and can:
Accept provisions as-is
Modify scope (tighten/loosen requirements)
Add/remove exemptions
Adjust standards/thresholds
These provisions will be refined in Step 5 based on strategic analysis

STEP 5: Strategic Audience Analysis
What AI does:
Identifies who will oppose the bill:
Industry groups affected
Political constituencies
Unions
Local economic interests
Analyzes jurisdiction-specific context:
Which industries are economically important here?
Recent political trends (shift toward/away from this policy?)
Geographic values (conservative vs. progressive area?)
Existing dependencies (does economy rely on regulated industry?)
Suggests language modifications to reduce opposition:
Add exemptions for vulnerable groups
Include phase-in periods to ease transition
Partner with unions/businesses through carve-outs
Estimates impact of each modification on passage likelihood
Example:
Policy goal: Ban single-use plastics in California grocery stores

Opposition Analysis:
1. California Grocers Association (6,000 stores)
   - Concern: Compliance costs estimated at $50M annually
   - Influence: HIGH - represents major employers statewide
   - Current stance: Likely to oppose

2. Plastics Manufacturers Union (Local 234)
   - Concern: Job losses (estimated 2,000 jobs)
   - Influence: MEDIUM - politically active union
   - Current stance: Definite opposition

3. Small Business Owners
   - Concern: Can't afford alternatives as easily as big chains
   - Influence: MEDIUM - sympathetic constituency
   - Current stance: Likely to oppose

Strategic Recommendations to Reduce Opposition:

Recommendation 1: Add retail exemption for stores <5,000 sq ft
- Removes: ~3,000 small businesses from requirements
- Reduces opposition: Small business groups become neutral
- Historical data: 10 of 12 passed bills included this exemption
- Cost to goal: Minimal (small stores account for only 12% of plastic bag usage)
- AI RECOMMENDS: Include this

Recommendation 2: Add 12-month phase-in period
- Benefit: Gives businesses time to find suppliers, train staff
- Reduces opposition: Grocers Association might become neutral
- Historical data: 11 of 12 passed bills had 6-18 month phase-in
- Cost to goal: Delays implementation by 1 year
- AI RECOMMENDS: Include this

Recommendation 3: Add retraining fund for displaced workers
- Benefit: Union support instead of opposition
- Cost: $5M one-time appropriation
- Historical data: 4 of 12 passed bills included this
- Reduces opposition: Union becomes supporter
- AI RECOMMENDS: Consider this (optional but helpful)

With Recommendations 1+2: Estimated passage likelihood increases from 45% to 78%
Why this matters:
Bills fail because of political opposition, not technical flaws
Understanding WHO opposes and WHY lets you shape language strategically
Small modifications (exemptions, timelines) can flip opponents to neutral
This is what consultants charge $50K+ to figure out
Output to user:
List of likely opponents with reasons
Strategic recommendations with trade-offs
Estimated impact on passage likelihood for each recommendation
User decides which modifications to include

STEP 6: Pattern Analysis from Historical Bills
What AI does:
Analyzes all similar bills (passed + failed) for patterns:
Which specific language phrases appear more in passed bills?
Which provisions correlate with success?
Which provisions correlate with failure?
Calculates success rates for different approaches:
"Bills using 'market-based mechanisms' language passed 73% of the time"
"Bills using 'carbon tax' language passed 22% of the time"
Provides in-line suggestions as user reviews draft:
Highlights risky language with warnings
Suggests alternative phrasing with better success rates
Explains WHY certain language works better
Example insights AI might provide:
In-line suggestion 1:
Your draft says: "Violators shall be fined $10,000"
Pattern analysis: Bills with fixed fines failed 67% of the time
Better approach: "Violators shall be fined up to $10,000" (passed 82% of the time)
Why: Gives judges discretion, seen as less punitive, reduces opposition
Click to apply this change

In-line suggestion 2:
Your draft says: "This act takes effect immediately upon passage"
Pattern analysis: Immediate enforcement caused 8 of 11 similar bills to fail
Better approach: "This act takes effect 12 months after passage" (10 of 12 passed)
Why: Phase-in period reduces business opposition
Click to apply this change

In-line suggestion 3:
Your draft says: "The California Department of Environmental Protection shall enforce..."
No issues detected: This language appears in 9 of 12 passed bills
Why this matters:
Subtle wording differences change outcomes
Humans can't manually analyze hundreds of bills across states
AI can spot patterns that even expert consultants miss
This is the "secret sauce" - the 1,000x faster analysis
Output to user:
As user reviews draft, AI highlights sections with color coding:
GREEN: Language matches successful patterns
YELLOW: Alternative phrasing might improve success rate
RED: This language appears more in failed bills - risky
Click any highlighted section to see alternative suggestions
Shows data: "Bills with this language passed X% vs. Y%"
“PHASE 2 Complete…PHASE 3 Loading”

PHASE 3: PROFESSIONAL POLISH
These sections are what separate amateur bills from professional consultant-quality bills
STEP 6.5: Draft Legislative Intent Section (Findings and Declarations)
User provides at start: Uploads (if any) existing/gathered research documents, studies, or relevant sources to cite and use for drafting
What this is:
A section at the beginning of the bill that explains WHY it's needed
Not legally binding, but courts reference it when interpreting the law later
Politically important - builds the case for why legislators should vote yes
What AI does:
Generates "Findings and Declarations" section with:
(a) Problem statement: "X poses a threat to public health/economy/environment"
(b) Specific harms with data: "Studies show X causes Y deaths/costs $Z annually"
(c) Why current law is insufficient: "Existing regulations don't address..."
(d) Why this bill is necessary: "Only comprehensive legislation can..."
(e) Expected benefits: "This bill will reduce X by Y%, saving $Z annually"
(f) Policy rationale: "As a leader in..., [Jurisdiction] has a responsibility to..."
Takes sources given by user (if uploaded) + Searches for relevant statistics and studies to cite
Models structure after successful bills like AB-32
CRITICAL: User must verify data accuracy
Example:
SECTION 2: FINDINGS AND DECLARATIONS

The Legislature finds and declares all of the following:

(a) Single-use plastic bags pose a serious threat to California's marine ecosystems, urban environments, and waste management infrastructure. Over 19 billion plastic bags are used annually in California, with an estimated 3-5% becoming litter that pollutes waterways and harms wildlife.

(b) Plastic bag litter costs California municipalities approximately $428 million annually in cleanup and waste management expenses, diverting funds from other essential services.

(c) Marine wildlife ingests an estimated 2.4 million plastic bags annually in California coastal waters, causing injury and death to protected species including sea turtles, seabirds, and marine mammals.

(d) Existing voluntary programs and industry initiatives have failed to significantly reduce plastic bag consumption, which has increased 8% since 2015 despite public awareness campaigns.

(e) Comprehensive legislation is necessary to achieve meaningful reduction in single-use plastic bag consumption and its associated environmental and economic harms.

(f) California has long been a national leader in environmental protection and waste reduction. This legislation continues that tradition and will serve as a model for other states.

(Note: AI generated this based on user goal + research. User must verify all statistics are accurate and current.)
Why this matters:
Courts use this section to interpret ambiguous parts of the law
Legislators reference this when deciding how to vote
Media quotes this when covering the bill
Without this, bill looks amateur
Output to user:
AI drafts full Findings section (typically 1-3 pages)
Cites sources for all statistics
User reviews and edits for accuracy

STEP 6.6: Define Implementation & Enforcement
User provides at start: Uploads/Enters (if any) existing positioning documents or relevant information/requests to use for drafting (asking them to format info in the structure shown below) 
What this is:
WHO enforces the law
WHAT penalties for violations
WHEN it takes effect
HOW compliance is monitored
Why bills fail without this:
"Suggestion" bills with no enforcement mechanism are ignored
If you don't specify an agency, no one has authority to enforce
If you don't specify penalties, there's no consequence for violations
What AI does:
Identifies appropriate enforcement agency based on:
Bill topic (environmental → Environmental agency)
Jurisdiction (state bill → state agency, federal → federal agency)
Historical precedent (which agency handled similar bills?)
Suggests penalty structure based on similar successful bills
Generates timeline:
Effective date (when law starts)
Compliance deadline (when entities must comply)
Reporting dates (when regulated entities report to agency)
Specifies rule-making authority (can agency create additional regulations?)
Example:
PART 5: ENFORCEMENT AND IMPLEMENTATION

Section 501: Enforcement Authority
(a) The California Department of Resources Recycling and Recovery (CalRecycle) shall enforce the provisions of this division.

(b) CalRecycle shall adopt regulations necessary to implement this division no later than January 1, 2027.

Section 502: Penalties
(a) Any retail establishment that violates Section 301 (prohibition on single-use plastic bags) shall be subject to administrative penalties as follows:
   (1) First violation: Written warning
   (2) Second violation: $500 fine per day of non-compliance
   (3) Third and subsequent violations: $1,000 fine per day of non-compliance

(b) Penalties shall be deposited into the Environmental Protection Fund established under Section 12345 of the Public Resources Code.

Section 503: Compliance Monitoring
(a) Retail establishments subject to this division shall submit annual compliance reports to CalRecycle by March 1 of each year, beginning March 1, 2028.

(b) CalRecycle shall conduct random compliance inspections and may require documentation to verify compliance.

Section 504: Effective Date
(a) This division takes effect on January 1, 2028, except as follows:
   (1) CalRecycle rule-making authority (Section 501(b)) takes effect immediately upon enactment
   (2) Retail establishment compliance (Section 301) takes effect 12 months after CalRecycle adopts regulations

(Why: 12-month phase-in period reduces opposition and gives businesses time to comply)
Why this matters:
Without enforcement, law is meaningless
Legislators will ask "Who enforces this?" - must have clear answer
Penalty structure must be realistic (too harsh = opposition, too weak = ignored)
Output to user:
AI suggests appropriate agency
AI generates penalty structure based on similar bills
AI creates implementation timeline
User reviews and can adjust amounts/dates

STEP 6.7: Fiscal Structure (California-Specific)
What this step produces:
Fiscal language for bill text (legal, binding)
Why bills fail without this:
Bills with unclear fiscal effects get held in Appropriations Committee
Missing mandate language (Article XIII B) procedurally kills bills affecting local governments
Vague funding sources trigger "General Fund impact" assumptions
"Unknown cost" or "needs General Fund" = automatic committee hold
What AI does:
PART A: Generates Bill Text (Statutory Fiscal Language)
AI determines if bill needs fiscal sections by checking:
Does it create regulatory duties? → Fee authority section
Does it impose penalties/fines? → Revenue deposit section
Does it affect local governments? → MUST include mandate disclaimer
Does it appropriate money? → Appropriation section (rare)
AI then generates California-standard clauses:
Fee Authority (when bill creates regulatory program):
"The [agency] may adopt, by regulation, a schedule of fees to be paid by [regulated entities] in an amount sufficient to recover the reasonable costs of administering this division."
Revenue Deposit (when fees/penalties collected):
"Revenues collected pursuant to this section shall be deposited into the [Fund Name] and shall be available, upon appropriation by the Legislature, for purposes of this division."
No Appropriation Statement (most bills):
"This act does not make an appropriation."
State Mandate Disclaimer (REQUIRED if affects local governments):
"No reimbursement is required by this act pursuant to Section 6 of Article XIII B of the California Constitution because [reason]."
Legislative Intent (optional, strategic):
"It is the intent of the Legislature that this division be implemented using existing resources and fee revenues to the extent feasible."

STEP 6.8: Add Standard Legal Protection Clauses
What these are:
Boilerplate legal language that professional bills always include
Protects bill from being entirely struck down if one part is invalid
Clarifies relationship to existing laws
Prevents conflicts with other agencies
What AI does:
Auto-inserts appropriate clauses based on jurisdiction
Minimal user review needed (standard language)
The 4 standard clauses:
1. Severability Clause (CRITICAL):
Section 701: Severability
The provisions of this division are severable. If any provision of this division or its application to any person or circumstance is held invalid, that invalidity shall not affect other provisions or applications that can be given effect without the invalid provision or application.

(Why: If court strikes down one section, rest of bill survives. Without this, entire bill fails if any part is unconstitutional.)
2. Savings Clause:
Section 702: Relationship to Other Laws
(a) Nothing in this division shall relieve any person, entity, or public agency of compliance with other applicable federal, state, or local laws or regulations.

(b) This division establishes additional requirements and does not supersede or replace existing environmental protection laws.

(Why: Clarifies this ADDS to existing law, doesn't replace it. Prevents "but we're already regulated!" arguments.)
3. Non-Preemption Clause (LOCAL BILLS ONLY):
Section 703: Local Authority Preserved
This ordinance establishes minimum standards for [subject matter]. Nothing herein shall prevent the City of [X] from adopting more stringent requirements in the future, nor shall it prevent the State of [Y] from enacting legislation that imposes stricter standards.

(Why: Local laws can be overridden by state law. This clarifies the local law is a floor, not a ceiling.)
4. Preservation of Authority:
Section 704: Other Agency Authority
Nothing in this division shall be construed to:
(a) Affect the existing authority of the Public Utilities Commission
(b) Limit the authority of local governments to enforce their own ordinances
(c) Supersede the jurisdiction of the California Coastal Commission

(Why: Prevents turf battles with other agencies who claim "this interferes with our authority.")
Why this matters:
Professional bills ALWAYS include these
Without severability clause, one typo can invalidate entire bill
Without savings clause, regulated entities claim "double regulation"
Signals you know what you're doing
Output to user:
AI auto-generates and inserts these clauses
User just reviews to make sure agency names are correct
“PHASE 3 Complete…PHASE 4 Loading”

PHASE 4: FINAL REVIEW
STEP 7: Legal & Constitutional Scan
What AI checks:
1. Conflict with Existing Laws:
Federal Preemption: Does federal law prohibit states/cities from regulating this?
Example: Cities can't regulate immigration (federal authority only)
State Preemption (for local bills): Does state law prohibit cities from regulating this?
Example: Some states prohibit cities from banning plastic bags
Conflicting Laws: Does this contradict existing laws in same jurisdiction?
Example: New law says X is banned, old law says X is required
2. Constitutional Issues:
Commerce Clause: Does this restrict interstate commerce unconstitutionally?
Takings Clause: Does this require compensation for property taken?
Equal Protection: Does this treat similar entities differently without justification?
Due Process: Does this provide fair notice and hearing procedures?
First Amendment: Does this restrict speech/religion unconstitutionally?
3. Structure & Formatting:
Citation style correct for jurisdiction?
Section numbering sequential and correct?
Cross-references accurate (Section 5 actually references Section 3)?
Enacting clause matches jurisdiction requirements?
Required legal language included?
What AI does:
Scans bill text for:
1. References to laws that might conflict
2. Provisions that might violate constitutional rights
3. Structural errors (wrong numbering, missing sections)
4. Formatting mistakes (wrong citation style)

Flags potential issues:
HIGH RISK: "This provision may violate Commerce Clause - consult attorney"
MEDIUM RISK: "Similar provisions challenged in 3 states - review carefully"
LOW RISK: "No obvious conflicts detected"

Suggests fixes:
"To avoid preemption, add: 'This section applies only to intrastate commerce'"
"To avoid takings issue, add: 'with just compensation as required by law'"
Example output:
Legal & Constitutional Scan Results:

No federal preemption issues detected
   (Plastic bags are not federally regulated - states/cities can regulate)

POTENTIAL ISSUE: State Preemption
   California AB-2026 (passed 2019) prohibits cities from banning specific products
   
   Risk Level: MEDIUM
   
   Recommendation: Add language clarifying this is a "statewide" ban, not city-level
   Suggested fix: "The Legislature hereby exercises statewide authority pursuant to..."
   
   Alternative: Remove this provision and focus only on state-level regulation

POTENTIAL ISSUE: Commerce Clause
   Provision 3(b) might restrict interstate commerce by requiring in-state manufacturing
   
   Risk Level: MEDIUM
   
   Cases where similar provisions were challenged: [links to 3 cases]
   
   Recommendation: Revise to apply equally to in-state and out-of-state manufacturers
   Suggested fix: Replace "manufactured in California" with "sold in California"

No Equal Protection issues detected

Structure & Formatting:
   ✓ Citation style correct (California format)
   ✓ Section numbering sequential
   ✓ Enacting clause correct
   ✓ All required sections present
   
Minor formatting issue: Section 402 cross-reference
   "...as defined in Section 302..." but Section 302 doesn't define this term
   Suggestion: Change to "Section 303" or add definition to Section 302

Overall Assessment: MEDIUM RISK
Recommendation: Address state preemption and commerce clause issues before introduction.
Why this matters:
One constitutional flaw = entire bill struck down by courts
Preemption issues = bill is legally void, wastes everyone's time
Formatting errors = bill rejected by legislative counsel before even being introduced
Output to user:
Color-coded risk assessment (green/yellow/red)
Specific issues flagged with case law references
Suggested fixes with example language

FINAL BILL STRUCTURE (All 8 sections assembled):
Short Title: "..."
Findings and Declarations: Why bill is needed
Definitions: Legal definitions of key terms
Core Provisions: What the bill actually does (main substance)
Implementation & Enforcement: Who enforces, penalties, timeline
Fiscal Structure (California-Specific)
Legal Protection Clauses: Severability, savings clause, etc.
Effective Date: When law takes effect
Product outputs as downloadable PDF with all sections assembled.

SUMMARY: Complete Process Flow
USER INPUT:
Jurisdiction + Policy Goal
    ↓
STEP 1: Load Templates
→ Output: Bill structure requirements
    ↓
STEP 2: Research Similar Bills
→ Output: 23 similar bills, 12 passed, 11 failed
    ↓
STEP 3: Extract & Adapt Provisions
→ Output: Language borrowed from successful bills
    ↓
STEP 4: Draft/Get User-Provided Definitions
→ Output: 2-3 options per term, user chooses scope
    ↓
STEP 4.5: Draft Core Provisions
    ↓
STEP 5: Audience Analysis
→ Output: Opposition analysis + strategic recommendations
    ↓
STEP 6: Pattern Analysis
→ Output: In-line suggestions ("this language passed 73% vs 22%")
    ↓
STEP 6.5: Draft Findings Section
→ Output: Legislative intent section
    ↓
STEP 6.6: Implementation/Enforcement
→ Output: Agency, penalties, timeline
    ↓
STEP 6.7: Fiscal Impact
→ Output: Cost estimate + funding source
    ↓
STEP 6.8: Legal Protection Clauses
→ Output: Severability, savings clause, etc.
    ↓
STEP 7: Legal/Constitutional Scan
→ Output: Risk assessment + flagged issues
    ↓
FINAL BILL PDF:
Complete professional bill ready for introduction 

AI-POWERED LEGISLATIVE DRAFTING & STRATEGY 
THE PROBLEM
The U.S. government spends over $100B annually on consulting. A significant portion of this is devoted to policy research and legislative support, which is often slow and expensive for organizations trying to draft effective bills. Expensive & Slow Bill Drafting: Current process: 6-12 weeks to research similar bills and draft legislation, $50K-$2M per engagement, high failure rates because drafters don't know what worked or failed in other states.

Who Suffers (Ranked by target priority/ROI in 12 week period):
(15% effort- Free: Gives us story + case studies to use on application video) 10 Youth organizations lack expertise to research successful bill templates and amendments
(70% effort: Our Source of Income) 25-30 engaged Small advocacy groups can't afford $50K+ consultants and draft bills that fail predictably OR Trade Associations
Scraper (by end of week, shortlist 500-1000 groups)
Currently Done: [Relevant NTEE codes finalized] → Next: Pick 10-15 NTEE codes → Get around information for ~10k-20k orgs → Pick and shortlist ~500-1000 to cold email
Other lines or client1s act as proof of concept for targeting these advocacy groups who we charge
(10% effort- Free: Gives us easy line for growth, user engagement, and credibility when approaching advocacy groups) 10 Under-Grad Policy/Grad-Students at Community Colleges and University Policy Clubs (like at UCB or top Unis) or Law School Legal Clinics (students that draft policy bills)
Targeting well-known policy clubs focused on bill-making or advising process and offering for all club members
Phrased As: "Used by UC Berk, GSSP policy students..."
Can always convert once the 12-week mark, if we have a strong userbase and want to target the higher funded clubs that can afford it
(5% effort- Offer Free Pilot) Policy think tanks spend weeks manually researching cross-state patterns for model legislation
Even one, would be really good and give us credibility
Can use Prof connections to get in touch with mid-sized or well known think tanks 

(After the 12-week mark aka. post-YC App and once we grow a larger userbase & credibility):
Junior policy staffers work 60+ hours weekly researching what similar bills passed in other states
Small lobbying firms miss patterns across states because manual analysis is too slow (too long conversion period + need stronger traction/backing)
Government agencies pay Deloitte and Accenture millions for legislative strategy AI can generate in seconds

Unequal Access: Wealthy corporations afford $2M consulting for legislative strategy (analyzing which similar bills passed, which failed, what amendments worked, coalition-building tactics). Small nonprofits draft bills blind, reinventing the wheel without data on what works.

Fragmented Knowledge: No single platform tells you: "12 states passed plastic bag bans, but only the 7 with retail exemptions succeeded" or "bills with X amendment language pass 3x more often." Analysts manually compare hundreds of bills across LexisNexis, StateNet, and legislative archives.

CURRENT SOLUTIONS & GAPS
Traditional Consulting (Deloitte, Accenture, McKinsey): $50K-$2M per engagement, 6-12 weeks timeline.
Gap: Manual, slow, inaccessible. They research past bills and draft strategy, exactly what AI should do.
Legislative Tracking Software (FiscalNote, Quorum, Bloomberg Gov): $10K-$50K+ annually.
Gap: Defensive monitoring only, tracks threats but doesn't help you draft legislation or analyze what bill language succeeds.
Legal Research Platforms (Westlaw, LexisNexis): $105-$295/month per user.
Gap: Find individual laws, don't analyze patterns across 50 states or generate model legislation.
Fed10 (YC W26): "Legislative consulting firm staffed by AI agents."
Gap: CRM-focused for lobbyist relationship management, not bill drafting or success pattern analysis.

Key Market Gap: Nobody offers offensive legislative intelligence, AI that analyzes what similar bills worked/failed across all states and generates winning model legislation with strategic playbooks.

OUR SOLUTION

Subscription-based AI platform ($500-$1K/month for small orgs; $5K+ for enterprises) that drafts winning legislation by analyzing historical bill data across all 50 states.

Core Value Proposition: Instead of hiring consultants to research which plastic bag ban language worked in 12 states, upload your policy goal → AI analyzes all similar bills → generates model legislation with provisions proven to pass → strategic playbook for amendments, timing, and coalitions

Core Principles: Speed (5 seconds vs. 6 weeks), intelligence (strategic insights not just data), transparency (every recommendation cited with bill numbers), affordable access ($500 vs. $2M), human-in-the-loop (AI drafts, humans decide).

MVP FEATURES

Feature 1: Compliance Scanner 
Defensive analysis to avoid legal conflicts.
Upload draft bill → AI scans for conflicts with existing federal/state laws, constitutional issues.
[ADDITION] Not only does AI improve the bill itself, but also provides feedback for the language of the bill, based on the structure of previously written bills, and comparing the draft bill with these bills, to help new writers improve and learn the bill writing process faster
Output: Legal conflicts with citations, constitutional risks, recommended amendments, risk score, writing updates [ADDITION].
Example:  

Feature 2: Legislative Strategy Builder 
Offensive bill drafting powered by historical success data.
Input: Describe policy goal ("ban single-use plastics in grocery stores")
Output:
Success rate analysis: 23 similar bills across states (12 passed, 11 failed)
What worked/failed: Bills with retail exemptions passed 2x more often; bans without phase-in periods failed 80% of the time
Model legislation template: AI-generated draft bill with winning provisions from successful states
State-by-state viability assessment: "High chance in CA/OR, moderate in CO, low in TX"
Strategic playbook: Optimal timing (introduce Q1 vs. Q3), coalition-building tactics, amendment strategy
Example: Environmental nonprofit wants plastic bag ban → AI finds 23 similar bills → identifies that bills with retail exemptions and 12-month phase-ins pass 2x more → generates model legislation combining Maine's exemption language + Colorado's phase-in timeline → recommends partnering with grocery associations (successful in 8/12 passed bills).
Time: 5 seconds vs. 6+ weeks (1,000x faster)
Cost: $500/month subscription vs. $50K-$2M consulting (100-4,000x cheaper)

Feature 3: Real-Time Bill Monitoring Dashboard
Track similar bills across all states with AI alerts when relevant bills pass/fail.
Integration with Strategy Builder to update success pattern analysis in real-time.

Feature 4: Citation & Source Transparency
Every finding cited with bill numbers, statute references, confidence scores, source links.
Audit trail showing analysis history.

MARKET RESEARCH

Growing Multi-Billion Dollar Market:
Government consulting market: $100B+ annually
U.S. lobbying spending: $4.5B in 2024 (all-time high)
Legal research software: $10K-$100K+ per enterprise
Total addressable market: $130B+

Massive User Base: 50 state legislatures, Congress, 12,000+ local governments, 394 lobbying firms with $1M+ revenue, thousands of law firms, advocacy organizations, Fortune 500 government affairs teams.

Market Validation:
FiscalNote serves 5,000+ clients at $10K-$50K+ pricing (but only does tracking, not drafting)
Brazilian Supreme Court AI (VICTOR) cuts policy analysis from 44 minutes → 5 seconds (UC Berkeley research)
Legislative consulting is massive but entirely manual, ripe for AI disruption

OUR DIFFERENTIATION

We're not a tracking tool or research database. We're an AI-powered legislative drafting engine that analyzes successful/failed bills across all 50 states to generate winning model legislation and strategic playbooks.

Think: "Replacing Deloitte's bill drafting consultants with AI" not "better bill tracking."
Unique moat: Offensive legislative intelligence, nobody else analyzes historical bill success patterns to generate model legislation.

EXECUTION PLAN (12-WEEK SPRINT)

Week 1: Research & Refinement
Meet with UC Berkeley GSPP professor on legislative drafting workflows
Competitor deep dive (FiscalNote, Quorum, Fed10)x
Build outreach list of 100+ target organizations (advocacy groups, trade associations, lobbying firms)

Week 2: Build MVP Demo
Web form: "Describe policy goal" → AI generates model legislation + success analysis
Backend: Claude API/GPT-4, database of 50-100 successful/failed bills from key states
Output: PDF with model bill, success pattern analysis, strategic recommendations
Goal: Functional 5-minute demo

Week 3: Network Demo Sprint
Run 15-20 demos with warm contacts (UN, IGF, Berkeley, YC)
Collect feedback on bill drafting workflow, willingness to pay
Goal: 3-5 testimonials, 10-15 referrals, 2-3 "I'd pay for this"

Week 4: Product Refinement + Expand Outreach
Update MVP based on feedback
Email 10-15 referrals, post on LinkedIn/policy Twitter
Goal: 10-15 new demo calls scheduled

Week 5-6: Cold Outreach to Target Customers
Segment: 50 small/mid advocacy orgs, 30 lobbying firms, 20 law firms
Send 20 emails/day offering free bill analysis
Set up Stripe, finalize pricing ($3,500/year Starter, $10K/year Pro)
Goal: 5-10 paying customers ($35K-$100K ARR), 20-30 free users

Week 7-8: Build Self-Serve Funnel
Public landing page with embedded Strategy Builder
Automated onboarding emails
Content marketing: Analyze trending bill on Twitter/LinkedIn
Goal: 10-15 paying customers ($5K-$15K MRR), 50-100 free users

Week 9-11: Scale What Works + YC Application
Double down on best-performing channels
Launch 1-2 partnerships (bar associations, policy schools)
Prepare YC application with metrics, demo video, pitch deck
Goal: 25-40 paying customers ($15K-$40K MRR), 100-150 free users, 15-20% WoW growth

SUCCESS METRICS (WEEK 11 TARGETS)
25-40 paying customers ($15K-$40K MRR)
100-150 free tier users
5-10 enterprise prospects ($10K+ contracts)
10+ testimonials from diverse segments
3-5 case studies with quantified ROI (e.g., "drafted bill in 5 seconds vs. 6 weeks")
15-20% week-over-week growth

WHY WE'LL WIN
Massive, Proven Market: $100B+ government consulting market, YC's stated thesis
Validated Technology: Brazilian courts already use AI for this (44 min → 5 sec)
No Direct Competition: FiscalNote/Quorum are defensive trackers. Fed10 is CRM-focused. Nobody does offensive bill drafting with historical success analysis.
Affordable & Scalable: $500-$5K/month vs. $2M consulting, democratizing elite legislative intelligence
Transparent & Trustworthy: Every recommendation cited with bill numbers and confidence scores
Political Tailwinds: Pressure to cut government waste + AI adoption = perfect timing

RISKS & MITIGATIONS
Legal liability for incorrect analysis: Clear disclaimers ("research tool, not legal advice"), confidence scores, human-in-the-loop, E&O insurance
Government procurement is slow: Start with advocacy orgs/lobbying firms (faster sales), build case studies, then sell to government
Data access (bill databases expensive): Start with public data, partner with legal platforms later, build own database over time
Competition from incumbents: Move fast on unique offensive feature (bill drafting AI), focus on user experience and transparency

Ask Prof:

How does his policy consultation firm get clients, through which means:

What does the work usually look like for policy consultants (is it pay per job or pay per hour per consultant – how many consultants in a firm and what does workflow look like), policy bills, documents, or what stakeholder group (advocacy groups, youth-led orgs, or governments)?

Also Ask: Based on our product idea, what types of organizations should we be targeting (use the list given above as a starting point). After this, ask, what are the best ways to find these organizations in bulk for outreach?

Fetches and returns the cleaned text content of a webpage containing statute text.. Use this to retrieve actual law text from California or federal legal databases.

For California Database
