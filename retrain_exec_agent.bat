@echo off
rem Retrain company-diagnosis agent with fixed corpus (my_data17 v2, ~6h on RTX 5060 8G)
rem Close games / heavy apps first. Log: train17.log (same dir as yaml)
cd /d D:\anaconda\LlamaFactory-main\LlamaFactory-main
"E:\conda\envs\llama311\Scripts\llamafactory-cli.exe" train my_train17.yaml
pause
