# CloudFront Only Access

Automatically update security groups to limit access for cloudfront. 

See https://aws.amazon.com/blogs/security/how-to-automatically-update-your-security-groups-for-amazon-cloudfront-and-aws-waf-by-using-aws-lambda/

##Usage
Add following tags to SecurityGroups:

    Tags(Name='cloudfront', AutoUpdate='true', Protocol='http')
    Tags(Name='cloudfront', AutoUpdate='true', Protocol='https')