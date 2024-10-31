import logging
import os
import smtplib
import relecov_tools.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from jinja2 import Environment, FileSystemLoader


log = logging.getLogger(__name__)


class EmailSender:
    def __init__(self, config):
        self.config = config
        self.template_path = self.config.get("delivery_template_path_file")
        self.yaml_cred_path = self.config.get("yaml_cred_path")

        if not self.config:
            raise ValueError("Configuration not loaded correctly.")

        if not os.path.exists(self.template_path):
            raise FileNotFoundError(
                f"The template file could not be found in path {self.template_path}."
            )

    def get_institution_info(
        self, institution_code, institutions_file="institutions.json"
    ):
        """
        Load the institution's information from the JSON file.
        """
        institutions_file = self.config.get(
            "institutions_guide_path", "institutions_guide.json"
        )
        institutions_data = relecov_tools.utils.read_json_file(institutions_file)

        if institutions_data and institution_code in institutions_data:
            return institutions_data[institution_code]
        else:
            print(f"No information found for code {institution_code}")
            return None

    def render_email_template(
        self, additional_info="", invalid_count=None, submitting_institution_code=None
    ):

        institution_info = self.get_institution_info(submitting_institution_code)
        if not institution_info:
            print("Error: The information could not be obtained from the institution.")
            return None, None

        institution_name = institution_info["institution_name"]
        email_receiver = institution_info["email_receiver"]

        env = Environment(loader=FileSystemLoader(os.path.dirname(self.template_path)))
        template = env.get_template(os.path.basename(self.template_path))

        email_template = template.render(
            submitting_institution=institution_name,
            invalid_count=invalid_count,
            additional_info=additional_info,
        )

        return email_template, email_receiver, institution_name

    def send_email(self, receiver_email, subject, body, attachments):
        credentials = relecov_tools.utils.read_yml_file(self.yaml_cred_path)
        if not credentials:
            print("No credentials found.")
            return

        sender_email = self.config["email_host_user"]
        email_password = credentials.get("email_password")

        if not email_password:
            print("The e-mail password could not be found.")
            return

        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        for attachment in attachments:
            with open(attachment, "rb") as attachment_file:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment_file.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={os.path.basename(attachment)}",
                )
                msg.attach(part)

        try:
            server = smtplib.SMTP(self.config["email_host"], self.config["email_port"])
            server.starttls()
            server.login(sender_email, email_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
            server.quit()
            print("Mail sent successfully.")
        except smtplib.SMTPException as e:
            log.error(f"Error sending the mail: {e}")
