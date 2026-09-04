#!/usr/bin/env python3

"""
NIZAMI CSV ENRICHMENT MODE

Pipeline:

CSV
 |
 |-- one row at a time
 |
 Supervisor
 |
 +-- Agent 1: Website intelligence
 +-- Agent 2: Contact discovery
 +-- Agent 3: Decision maker discovery
 +-- Agent 4: Service / technology analysis
 |
 Merge
 |
 Save enriched CSV


This module does NOT modify Chat Mode.
"""


import asyncio
import csv
import json
import time
from pathlib import Path
from datetime import datetime


OUTPUT_FIELDS = [
    "Website URL",
    "Company Name",
    "Phone Number",
    "Additional Phone Numbers",
    "Emails",
    "Social Links",
    "Keywords - Team",
    "Specification",
    "Relevancy",
    "Services",
    "Person Name",
    "Job Title"
]


DECISION_PRIORITY = """
Priority contacts:

1. Founder
2. CEO
3. Owner
4. Co-Founder
5. Managing Director
6. Partner
7. Sales Director
8. Business Development Director

Avoid:
- HR
- Recruiters
- Developers
- Employees
- Interns
"""


class CSVEnrichmentMode:


    def __init__(self, supervisor):

        self.supervisor = supervisor



    async def run(self):

        print(
            "\n=============================="
        )

        print(
            " NIZAMI CSV ENRICHMENT MODE"
        )

        print(
            "==============================\n"
        )


        csv_path = input(
            "CSV File Path > "
        ).strip()


        file = Path(csv_path)


        if not file.exists():

            print(
                "CSV file not found"
            )

            return



        rows = self.load_csv(file)


        print(
            f"\nLoaded {len(rows)} companies\n"
        )


        output_file = (
            file.parent /
            f"{file.stem}_enriched.csv"
        )


        completed = []



        for index,row in enumerate(rows,1):


            print(
                "\n--------------------------------"
            )

            print(
                f"Processing {index}/{len(rows)}"
            )


            print(
                row.get(
                    "Website URL",
                    ""
                )
            )


            try:

                enriched = await self.enrich_row(
                    row
                )


                completed.append(
                    enriched
                )


                self.save_progress(
                    output_file,
                    completed
                )


                print(
                    "Completed"
                )


            except Exception as e:


                print(
                    "FAILED:",
                    e
                )


                failed=row.copy()

                failed["Relevancy"]="FAILED"

                completed.append(
                    failed
                )


        print(
            "\n================================"
        )

        print(
            "CSV ENRICHMENT FINISHED"
        )

        print(
            output_file
        )

        print(
            "================================"
        )



    def load_csv(self,path):

        with open(
            path,
            "r",
            encoding="utf-8-sig"
        ) as f:


            reader=csv.DictReader(f)

            return list(reader)




    async def enrich_row(self,row):


        website=row.get(
            "Website URL",
            ""
        )


        task=f"""

You are a company intelligence system.

Analyze ONE company only.

Website:
{website}


Existing CSV Data:

{json.dumps(
    row,
    indent=2
)}


Collect:


COMPANY INFORMATION

- Company name
- Industry
- Services
- Business type


CONTACT INFORMATION

- Main phone number
- Additional phone numbers
- Official emails
- Social media links


TECHNICAL INFORMATION

- Technologies
- Platforms
- Frameworks
- Keywords


DECISION MAKERS

Find only:

{DECISION_PRIORITY}


Return JSON only:


{{
"Company Name":"",
"Phone Number":"",
"Additional Phone Numbers":"",
"Emails":"",
"Social Links":"",
"Keywords - Team":"",
"Specification":"",
"Relevancy":"",
"Services":"",
"Person Name":"",
"Job Title":""
}}

"""


        result = await self.run_agents(
            task
        )


        data=self.extract_json(
            result
        )


        merged={}



        for field in OUTPUT_FIELDS:


            if field=="Website URL":

                merged[field]=website


            else:

                value=data.get(
                    field,
                    ""
                )


                if not value:

                    value=row.get(
                        field,
                        ""
                    )


                merged[field]=value



        return merged




    async def run_agents(
        self,
        task
    ):

        """
        Uses all available agents.
        """

        agents=self.supervisor.discover_agents()


        jobs=[]


        for name,path in agents.items():

            jobs.append(
                self.supervisor.run_agent(
                    name,
                    path,
                    task
                )
            )


        results=await asyncio.gather(
            *jobs,
            return_exceptions=True
        )



        outputs={}



        for index,result in enumerate(results):

            name=list(
                agents.keys()
            )[index]


            if isinstance(
                result,
                Exception
            ):

                outputs[name]=(
                    "ERROR "
                    +
                    str(result)
                )

            else:

                outputs[name]=result



        return await self.merge_agents(
            task,
            outputs
        )




    async def merge_agents(
        self,
        task,
        outputs
    ):


        prompt=f"""

You are the CSV enrichment supervisor.


Original task:

{task}


Agent responses:

{json.dumps(
    outputs,
    indent=2
)}


Merge the information.

Rules:

- Prefer verified data
- Remove duplicates
- Prefer CEO/founder/owner contacts
- Return JSON only

"""


        if hasattr(
            self.supervisor,
            "think"
        ):

            return await self.supervisor.think(
                prompt
            )


        return json.dumps(outputs)




    def extract_json(
        self,text
    ):


        try:

            return json.loads(
                text
            )

        except:


            start=text.find(
                "{"
            )

            end=text.rfind(
                "}"
            )


            if start!=-1 and end!=-1:

                try:

                    return json.loads(
                        text[start:end+1]
                    )

                except:

                    pass



        return {}




    def save_progress(
        self,
        path,
        rows
    ):


        with open(
            path,
            "w",
            newline="",
            encoding="utf-8"
        ) as f:


            writer=csv.DictWriter(
                f,
                fieldnames=OUTPUT_FIELDS
            )


            writer.writeheader()

            writer.writerows(
                rows
            )