# Export CloudWatch Logs to S3

Export CloudWatch Logs using CloudWatch Events and Lambda (Called by a 
Step Function State Machine.)
  
>  Cloudwatch Events Step Function Trigger is not implemented in CloudFormation yet.

## Usage
 
1. Create a log export bucket using `CwLogsExportBucket` template.
2. Setup cloudwatch logs using `ExportCloudWatchLogsToS3` template.
3. Manually create a cloud watch rules which triggers stepfunction state machine
   weekly or daily.
