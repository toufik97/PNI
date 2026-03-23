this file is for defining the dtc rules:
it will go as prior doses and each will have edge cases:
1. 5 prior doses: nothing to add
2. 4 prior doses:
    - if age is between 5 years and 7 dtc2 else td
3. 3 prior doses:
    - if age is between 18 months and 3 years dtc1 then dtc2 (min 3.5 years interval and only if age is less than 7 years) else td
    - if age is bigger than 3 years and less than 5 years dtc1 then dtc2 (minimum 3.5 years interval and only if age is less than 7 years) else td
4. 2 prior doses:
    - if age is less than 18 months penta3 then dtc1(min 6 months interval) then dtc2(min 3.5 years interval and only if age is less than 7 years) else td
    - if age is between 18 months and 3 years penta3 then dtc1(min 6 months interval) then dtc2(min 3.5 years interval and only if age is less than 7 years) else td
    - if age is between 3 and 5 years dtc1 then dtc2(min 6 months) then dtc3(min 3.5 years and only if age is less than 7 years) else td
5. 1 prior dose:
    - if age is less than 18 months penta2 then penta3(min 28days) then dtc1(min 6 months interval) then dtc2(min 3.5 years interval and only if age is less than 7 years) else td
    - if age is between 18 months and 3 years penta2 then dtc1(min 28days) then dtc2 (min 6 months ) then dtc3(min 3.5 years and only if age is less than 7 years) else td
    - if age is between 3 and 7 years dtc1 then dtc2 (min 28 days) then dtc3 (min 6months) then dtc4 (min 3.5 years and only if age is less than 7 years) else td
6. 0 prior dose:
    - if age is less than 12 months proceed as normal 3 penta doses min 28 days interval then dtc1(18 months min 6 months) then dtc2(5years min 3.5 years only if age is less than 7 years) else td
    - if age is between 12 months and 3 years 2 doses of penta and 1 with dtc (min 28 days interval) then dtc2(min 6 months) then dtc3(min 3.5 years and only if age is less than 7 years) else td
7. 0 prior dose and age is bigger than 7years:
    - td1  then td2 (min 28 days) then td3 (min 28 days) then td4 (min 6 months) then td5 (min 1 years )
    
some general rules:
- td is given at 7 years and above
- dtc is not given after 7 years