# Submission

Fork URL: <!-- paste the URL of your fork here -->

## Files to commit

- [ ] `notes.md` with your CIDR plan and the commands you used (optional)

## Questions

Answer in your own words. Where a question asks for output, paste it in a code block.

### Q1. Paste your CIDR plan: the VPC, the six subnets (two per tier, two zones) and why you chose these sizes. How many usable addresses does AWS leave in a `/24`?

**Your answer:**

<!-- replace this line with your answer -->

### Q2. Show the route table of each tier (`aws ec2 describe-route-tables`). Which one has the internet gateway, which has the NAT, which has neither, and what does that mean for the data tier?

**Your answer:**

<!-- replace this line with your answer -->

### Q3. Paste the security groups and the network ACL of the data tier. Why do you need both? Which one is stateful and what does that mean for the return traffic?

**Your answer:**

<!-- replace this line with your answer -->

### Q4. The auditor asks: "Can a host in the data subnets reach the internet?" Show two ways to prove the answer is no (route table, reachability analysis, a test).

**Your answer:**

<!-- replace this line with your answer -->

### Q5. Compare one NAT Gateway for both zones with one per zone. What does each cost per month and what fails when its zone goes down?

**Your answer:**

<!-- replace this line with your answer -->

### Q6. Paste the output of `./verify.sh`. It must end with **ALL CHECKS PASSED**.

**Your answer:**

<!-- replace this line with your answer -->

### Q7. **Tear down.** Paste the output of `./verify-teardown.sh`. It must end with **TEARDOWN VERIFIED**.

**Your answer:**

<!-- replace this line with your answer -->
