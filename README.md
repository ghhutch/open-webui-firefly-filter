# Open WebUI Adobe Firefly Filter
The Open WebUI Adobe Firefly Filter providse open web-ui admins to setup a filter that calls the Adobe [Firefly Services Generate Image V3 Asynchronous API endpoint](https://developer.adobe.com/firefly-services/docs/firefly-api/guides/api/image_generation/V3_Async/).

DISCLAIMER: At the time of writing this the code, it is still a prototype and has not been throuroughly tested.  This was built for exploratory purposes as a means to test Open WebUI's functionality and various ways to generate images.

Conceptual Use Case:
1. Use chat interface with an LLM to optimize a prompt. e.g. Play the role of a creative director and enhance my prompt: A dog and pony show
2. Once you have an optimized prompt, use the filter to genearate an image. e.g. /firefly A dog and pony at a circus doing acrobatics with a spotlight on the pony with colorful and moody lighting of various sizes in the background.
3. Further refine the prompt and generations.


## Pre-requisites
Get Credentials - If you don't already have a Firefly Services Client ID and Client Secret, retrieve them from your [Adobe Developer Console](https://developer.adobe.com/developer-console/docs/guides/services/services-add-api-oauth-s2s/#api-overview) project before reading further.  You may have to contact your Adobe Admin to get privileges to the Developer Console or for the Admin to go to the console and give you the keys. Securely store these credentials and never expose them in client-side or public code.

## Setup
*Create Function*
1. Admin Settings
2. Functions
3. Click + to add New Function
4. Copy and paste the filter code.
5. Save

*Configure Function*
1. Click on the value gear icon to configure the filter
2. Enter the client_id
3. Enter the client_secret
4. Optionally change the default size
   * Supported sizes for the output images with image3 are:
      * Square (1:1) - width 2048px, height 2048px
      * Square (1:1) - width 1024px, height 1024px
      * Landscape (4:3) - width 2304px, height 1792px
      * Portrait (3:4) - width 1792px, height 2304px
      * Widescreen (16:9) - width 2688px, height 1536px
      * Widescreen (16:9) - width 2688px, height 1512px
      * (7:4) - width 1344px, height 768px
      * (7:4) - width 1344px, height 756px
      * (9:7) - width 1152px, height 896px
      * (7:9) - width 896px, height 1152px
   * Supported sizes for the output images with image4 are:
      * (1:1) - width 2048px, height 2048px
      * (4:3) - width 2304px, height 1792px
      * (3:4) - width 1792px, height 2304px
      * (16:9) - width 2688px, height 1536px
      * (9:16) - width 1440px, height 2560px
6. Optionally change the default content class (photo, art)
7. Optionally change the model (image3, image3_custom, image4_standard, image4_ultra)
8. Save
9. Enable the filter
10. Click on the ... and enable global.  This will enable the filter across all models.  Alternatively, you can apply the filter to specific models within the model settings of the Admin Settings.

## Usage
Generate Adobe Firefly images when entering a message using the format:
/firefly {prompt}

For example:
/firefly a dog and pony show




