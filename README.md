# Collection of Reusable CloudFormation Templates

In the process of moving from kotaimen/cfn-templates to here, 
and ditch `troposphere` in favour of raw YAML templates.

See also:
 
 - https://github.com/awslabs/aws-cloudformation-templates
 

## Directory Structure

- `components` - resuable components grouped by services.
- `solutions` - solutions, depends on template files in `components`.
- `stacks` - sample `awscfncli` stack configuration.
- `cfnutil` - little python helper library for run `troposphere` templates.


## Note

To build troposphere templates you need to install `cfnutil` utilties first.